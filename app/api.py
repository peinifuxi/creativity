from openai import OpenAI
import json
from settings import settings  
import re
import ast
from typing import List, Tuple

def analyze_case_with_api(content):
    """调用DeepSeek API分析案件"""
    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,   
            base_url=settings.DEEPSEEK_BASE_URL  
        )
        
        first_line = content.strip().split('\n')[0]
        
        prompt = f"""
        分析案件，返回JSON格式，包含以下字段：
        1. title：必须是类似"张某、李某...案件类别判决书"的格式，第一行"{first_line}"如果是这种格式就保留，否则重新生成
        2. sort：刑事案件/民事案件/行政案件/其他（根据title中的案件类别判断）
        3. summary：800-1000字的详细摘要，**必须包含**以下信息：法院名称(court)、涉案人员(persons)、相关法律(laws)、纠纷描述(dispute)、案发地点(location)等关键内容，确保摘要完整涵盖案件要点
        4. keywords：5-10个关键词列表
        5. court：审理法院名称
        6. laws：涉及的相关法律条文列表（如["刑法第232条", "民法典第1045条"]）
        7. persons：所有涉案人员列表，每个人员包含角色和姓名（如[{{"role": "上诉人", "name": "张某"}}, {{"role": "被上诉人", "name": "李某"}}]）
        8. dispute：案件纠纷的简要描述
        9. location：案发地点
        
        内容：{content[:2000]}  # 增加输入内容长度
        """
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个法律分析助手，返回纯JSON。title格式必须是'人名...案件类别判决书'。摘要要详细完整，涵盖所有关键信息。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000  # 增加输出token数
        )
        
        raw_text = response.choices[0].message.content
        result = _safe_parse_json(raw_text)
        
        # 确保title格式正确
        title = result.get('title', '')
        if not ('判决书' in title or '裁定书' in title):
            title = first_line[:50]
        
        # 根据title确定sort
        sort = '其他'
        if '刑事' in title:
            sort = '刑事案件'
        elif '民事' in title:
            sort = '民事案件'
        elif '行政' in title:
            sort = '行政案件'
        
        # 处理persons字段，确保是列表
        persons = result.get('persons', [])
        if not isinstance(persons, list):
            persons = []
        
        # 处理laws字段，确保是列表
        laws = result.get('laws', [])
        if not isinstance(laws, list):
            laws = []
            
        # 获取摘要，如果太短就补充
        summary = result.get('summary', '')
        if len(summary) < 300:  # 如果摘要太短
            summary = summary + " " + "（完整摘要请参考案件详情）"
            
        return {
            "title": title[:50],
            "sort": sort,
            "summary": summary[:1000],  # 增加到1000字
            "keywords": result.get('keywords', [])[:10],
            "court": result.get('court', '')[:50],
            "laws": laws,
            "persons": persons,
            "dispute": result.get('dispute', '')[:300],  # 纠纷描述也加长
            "location": result.get('location', '')[:100]
        }
        
    except Exception as e:
        print(f"API调用失败: {e}")
        first_line = content.strip().split('\n')[0]
        sort = '其他'
        if '刑事' in first_line:
            sort = '刑事案件'
        elif '民事' in first_line:
            sort = '民事案件'
        elif '行政' in first_line:
            sort = '行政案件'
            
        return {
            "title": first_line[:50],
            "sort": sort,
            "summary": content[:800] + "...",  # 失败时也用更长的摘要
            "keywords": [],
            "court": "",
            "laws": [],
            "persons": [],
            "dispute": "",
            "location": ""
        }

def extract_entities_relations(content: str, hints: dict | None = None):
    """调用DeepSeek进行实体与关系抽取，返回图谱nodes/links 与 raw"""
    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        # 先验线索拼接（可选）
        hints_text = ""
        if hints:
            persons_hint = ", ".join([f"{p.get('name','')}/{p.get('role','') or '无'}" for p in hints.get("persons", []) if isinstance(p, dict) and p.get("name")])
            incident_hint = hints.get("incident") or ""
            location_hint = hints.get("location") or ""
            time_hint = hints.get("time") or ""
            hints_text = f"""
            先验线索（优先聚焦但以正文为准）：
            - 主要人物及角色（可能不全）：{persons_hint or '无'}
            - 关键事件/纠纷描述：{incident_hint or '无'}
            - 可能的地点：{location_hint or '无'}
            - 可能的时间：{time_hint or '无'}
            """
        prompt = f"""
        任务：对中文法律文书做实体与关系抽取，仅返回严格JSON（无任何多余文本）。
        知识图谱设计（请严格遵循）：
        - nodes：节点数组。每个节点形如：
          {{"id":"n1","type":"person|event|time|location","name":"张三/盗窃案发/2024年3月/北京市海淀区","role":"原告|被告|证人|法官|检察官|无"}}
          说明：
            * type 必须是 person、event、time、location 四类之一
            * 对于人物，尽量识别其角色（原告/被告/证人/法官/检察官等），未识别用“无”
            * id 唯一，建议 p1/e1/t1/l1 等格式
        - links：关系列表。每个关系形如：
          {{"source":"p1","target":"e1","relation":"参与"}}
          推荐关系值：参与(人物-事件)、发生于(事件-时间)、发生在(事件-地点)、涉及(事件-人物)、起诉(原告-被告)、被诉(被告-原告)
        要求：
        - 以“被告、原告”为图谱发散中心：请至少识别主要的被告/原告节点，并把与其相关的事件、时间、地点、其它人物通过关系连接出来
        - 控制规模：优先抽取2-4个“核心事件”，并可拆分为“准备→实施→结果”等子事件；每个事件尽量关联时间与地点；总节点建议 15-35 个
        - 确保 links 的 source/target 必须在 nodes 里存在
        - 重点聚焦“犯罪/违法事实本身的发生经过”，包括作案手段、受害对象、工具、后果、直接发生的地点与时间
        - 细节增强（尽量体现在事件名称与关系中）：
          * 作案方式/手段（如“撬锁”“入室”“勒索”“殴打”“网络转账”）
          * 工具/载具（“匕首”“钢管”“汽车”“银行卡/手机/微信/QQ”）
          * 受害对象与财物（“被害人姓名/单位”“金额/物品”）
          * 后果（“轻伤/重伤/死亡/财物损失金额”）
          * 事件间的先后（在名称中加“先/后”描述或创建 e2,e3 表示顺序）
        - 严格排除与法庭审理/裁判程序相关的信息（不要抽取以下内容作为节点或关系）：
          审判/审理/开庭/合议庭/宣判/判决/裁定/上诉/抗诉/公诉/检察/检察官/法官/书记员/审查起诉/合议等
        - 节点去重：同名人物或同义事件尽量合并为一个节点
        - 示例（仅作格式参考）：
          {{"nodes":[{{"id":"p1","type":"person","name":"张三","role":"被告"}},{{"id":"e1","type":"event","name":"入室盗窃"}},{{"id":"t1","type":"time","name":"2024年3月"}},{{"id":"l1","type":"location","name":"北京市海淀区"}}],
            "links":[{{"source":"p1","target":"e1","relation":"参与"}},{{"source":"e1","target":"t1","relation":"发生于"}},{{"source":"e1","target":"l1","relation":"发生在"}}]}}
        - 严格返回：{{"nodes":[...] ,"links":[...]}}（仅此对象）
        
        {hints_text}
        文书内容（最多前2000字）：
        {content[:2000]}
        """
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是信息抽取助手，只返回有效JSON，无解释。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2200
        )
        raw = response.choices[0].message.content
        data = _safe_parse_json(raw)
        nodes = data.get('nodes', [])
        links = data.get('links', [])
        # 兜底：保证基本结构与关键字段
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(links, list):
            links = []
        normalized_nodes = []
        seen_ids = set()
        for n in nodes:
            nid = n.get('id') or n.get('name')
            name = n.get('name', '')
            ntype = n.get('type', '')
            role = n.get('role', '')
            if not nid or not name:
                continue
            if ntype not in ('person', 'event', 'time', 'location'):
                # 尝试推断：含“年/月/日”判为 time；含“市/区/县/省/法院/路/街”判为 location；默认 event
                txt = name
                if any(k in txt for k in ['年','月','日','时']):
                    ntype = 'time'
                elif any(k in txt for k in ['市','区','县','省','法院','路','街','镇','村']):
                    ntype = 'location'
                else:
                    ntype = 'event'
            # 过滤法庭/审判相关节点
            trial_keywords = ['审理','审判','判决','裁定','开庭','合议庭','宣判','上诉','抗诉','公诉','检察','审查起诉']
            trial_roles = ['法官','书记员','检察官','公诉人','审判长','审判员','合议庭成员']
            if ntype == 'person' and role in trial_roles:
                continue
            if ntype == 'event' and any(k in name for k in trial_keywords):
                continue
            if ntype == 'location' and '法院' in name:
                # 法院地点属于审判相关，剔除
                continue
            if nid in seen_ids:
                continue
            seen_ids.add(nid)
            normalized_nodes.append({"id": nid, "name": name, "type": ntype, "role": role})
        normalized_links = []
        trial_relation_keywords = ['起诉','被诉','宣判','裁定','审理','审判','上诉','抗诉','公诉','检察']
        for r in links:
            s = r.get('source')
            t = r.get('target')
            rel = r.get('relation', '')
            if not (s and t):
                continue
            # 去除程序性关系
            if any(k in (rel or '') for k in trial_relation_keywords):
                continue
            # 保证端点仍存在
            if s in seen_ids and t in seen_ids:
                lconf = r.get('conf', 1.0)
                normalized_links.append({"source": s, "target": t, "relation": rel, "conf": float(lconf) if isinstance(lconf, (int,float)) else 1.0})
        # 事件合并（按时间+人物集合）
        merged_nodes, merged_links = _merge_events_by_time_and_persons(normalized_nodes, normalized_links)
        return {
            "persons": [n for n in merged_nodes if n.get('type') == 'person'],
            "graph": {"nodes": merged_nodes, "links": merged_links},
            "raw": data
        }
    except Exception as e:
        print(f"实体关系抽取失败: {e}")
        try:
            # 打印原始文本便于排查
            print(f"RAW_RESPONSE_START\n{raw}\nRAW_RESPONSE_END")
        except Exception:
            pass
        return {
            "persons": [],
            "graph": {"nodes": [], "links": []},
            "raw": {}
        }

# ===================== JSON 解析增强 =====================
def _safe_parse_json(raw_text: str):
    """
    尝试以更鲁棒的方式解析模型返回的JSON：
    1) 去除代码块围栏
    2) 提取最外层 { ... } 片段
    3) 原生 json.loads
    4) 失败则做一些常见修复：替换 None/True/False，去除行内注释与尾随逗号
    5) 再失败用 ast.literal_eval 兜底（支持单引号的Python风格）
    """
    if raw_text is None:
        raise ValueError("empty response")
    text = raw_text.strip()
    # 去掉围栏
    text = text.replace('```json', '').replace('```', '').strip()
    # 提取花括号之间的主体
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    # 先直接尝试
    try:
        return json.loads(text)
    except Exception:
        pass
    # 常见修复：布尔/空值、尾随逗号、注释
    fixed = text
    fixed = re.sub(r'//.*', '', fixed)  # 行内注释
    fixed = re.sub(r'/\\*.*?\\*/', '', fixed, flags=re.S)  # 块注释
    fixed = fixed.replace(': None', ': null').replace(': True', ': true').replace(': False', ': false')
    fixed = fixed.replace(':None', ': null').replace(':True', ': true').replace(':False', ': false')
    # 去除尾随逗号：}, ] 之前的逗号
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except Exception:
        pass
    # 最后兜底：Python风格字面量
    try:
        data = ast.literal_eval(fixed)
        if isinstance(data, (dict, list)):
            return data
    except Exception:
        pass
    # 进一步兜底：尝试提取/修复 nodes 与 links 两个数组，截断不完整对象
    try:
        salvage = _salvage_nodes_links(text)
        if salvage:
            return salvage
    except Exception:
        pass
    # 全部失败则抛出原始异常
    return json.loads(text)  # 让上层捕获并打印具体错误

def _split_complete_json_objects(array_inner: str) -> List[str]:
    """把形如 {..},{..},{ 未完 的内容，按花括号配对切成完整对象片段"""
    objs = []
    buf = []
    depth = 0
    in_str = False
    esc = False
    for ch in array_inner:
        buf.append(ch)
        if in_str:
            if esc:
                esc = False
            elif ch == '\\\\':
                esc = True
            elif ch == '\"':
                in_str = False
        else:
            if ch == '\"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth - 1)
                if depth == 0:
                    # 完成一个对象
                    obj_text = ''.join(buf).strip()
                    # 去掉可能的尾随逗号
                    if obj_text.endswith(','):
                        obj_text = obj_text[:-1]
                    objs.append(obj_text)
                    buf = []
    return objs

def _salvage_nodes_links(text: str):
    """从不完整输出中尽可能提取 nodes 与 links 两个数组，返回 dict"""
    # 去掉围栏
    t = text.replace('```json', '').replace('```', '')
    # 尝试宽松获取 nodes/links 内部内容（即使缺失收尾的 ']' 也能工作）
    def grab_array_inner(label: str) -> str:
        # 先用正则（完整闭合）
        m = re.search(rf'\"{label}\"\\s*:\\s*\\[(.*?)]', t, flags=re.S)
        if m:
            return m.group(1)
        # 否则宽松地从 '[' 开始取到文本末尾
        i = t.find(f'"{label}"')
        if i == -1:
            return ''
        j = t.find('[', i)
        if j == -1:
            return ''
        return t[j+1:]  # 取到末尾，后续用对象级配对切分

    nodes_inner = grab_array_inner('nodes')
    links_inner = grab_array_inner('links')
    if not nodes_inner and not links_inner:
        raise ValueError("no nodes/links found to salvage")
    node_objs = _split_complete_json_objects(nodes_inner)
    link_objs = _split_complete_json_objects(links_inner)
    # 解析各对象，跳过坏的
    nodes = []
    for s in node_objs:
        try:
            nodes.append(json.loads(s))
        except Exception:
            continue
    links = []
    for s in link_objs:
        try:
            links.append(json.loads(s))
        except Exception:
            continue
    return {"nodes": nodes, "links": links}

# ===================== 事件合并（按时间+人物集合） =====================
def _merge_events_by_time_and_persons(nodes, links):
    """
    合并策略：
    - 找到每个事件节点 e 的：
        1) 直连的唯一/主 time 节点（任选一个，优先第一个）
        2) 直连的 person 集合（按 id 去重、排序）
    - 将 key=(time_id or '') + tuple(sorted(person_ids)) 相同的多个事件合并为一个
    - 合并规则：
        * 事件名称合并：取长度最长的一条，若多条不同，名称后缀追加“（合并N）”
        * conf 取 max
        * attrs 合并为第一条的 attrs
        * 连接的其他边（location/amount/object等）求并集，重定向到新事件
    - 去重边：(source,target,relation) 唯一
    - 清理孤立节点：删除没有任何边的事件节点
    """
    id_to_node = {n["id"]: n for n in nodes}
    # 邻接
    nbr = {}
    for n in nodes:
        nbr[n["id"]] = set()
    for l in links:
        s = l.get("source")
        t = l.get("target")
        nbr.setdefault(s, set()).add(t)
        nbr.setdefault(t, set()).add(s)
    # 事件集合与键
    events = [n for n in nodes if n.get("type") == "event"]
    event_keys = {}
    for e in events:
        eid = e["id"]
        persons = []
        times = []
        for v in nbr.get(eid, set()):
            vn = id_to_node.get(v)
            if not vn:
                continue
            if vn.get("type") == "person":
                persons.append(vn["id"])
            elif vn.get("type") == "time":
                times.append(vn["id"])
        persons = sorted(list(set(persons)))
        time_id = times[0] if times else ""
        key = (time_id, tuple(persons))
        event_keys.setdefault(key, []).append(eid)
    # 合并映射
    remap = {}
    new_events = {}
    for key, eids in event_keys.items():
        if len(eids) <= 1:
            continue
        ev_nodes = [id_to_node[eid] for eid in eids if eid in id_to_node]
        # 名称选择与合并
        def safe_len(x): 
            try:
                return len(x)
            except Exception:
                return 0
        main = max(ev_nodes, key=lambda x: safe_len(x.get("name", "")))
        merged_name = main.get("name", "") if isinstance(main.get("name", ""), str) else "合并事件"
        if any((n.get("name") != merged_name) for n in ev_nodes):
            merged_name = f"{merged_name}（合并{len(ev_nodes)}）"
        merged_id = ev_nodes[0]["id"]
        merged_conf = max([n.get("conf", 1.0) if isinstance(n.get("conf", 1.0), (int,float)) else 1.0 for n in ev_nodes] + [1.0])
        merged_attrs = ev_nodes[0].get("attrs", {}) if isinstance(ev_nodes[0].get("attrs", {}), dict) else {}
        new_events[merged_id] = {
            "id": merged_id,
            "type": "event",
            "name": merged_name,
            "role": "",
            "conf": float(merged_conf),
            "attrs": merged_attrs
        }
        for eid in eids:
            if eid != merged_id:
                remap[eid] = merged_id
    if not remap:
        return nodes, links
    # 节点重建
    kept_nodes = []
    seen = set()
    for n in nodes:
        nid = n["id"]
        if n.get("type") == "event" and nid in remap:
            continue
        if n.get("type") == "event" and nid in new_events:
            if nid in seen:
                continue
            kept_nodes.append(new_events[nid])
            seen.add(nid)
        else:
            kept_nodes.append(n)
    # 边重建并去重
    dedup = set()
    kept_links = []
    for l in links:
        s = remap.get(l.get("source"), l.get("source"))
        t = remap.get(l.get("target"), l.get("target"))
        if s == t:
            continue
        k = (s, t, l.get("relation", ""))
        if k in dedup:
            continue
        dedup.add(k)
        kept_links.append({"source": s, "target": t, "relation": l.get("relation", ""), "conf": l.get("conf", 1.0)})
    # 清理孤立事件
    used = set()
    for l in kept_links:
        used.add(l["source"]); used.add(l["target"])
    kept_nodes = [n for n in kept_nodes if n["id"] in used or n.get("type") != "event"]
    return kept_nodes, kept_links
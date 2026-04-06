from openai import OpenAI
import json
import requests
import os
import re
import ast
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from settings import settings  

PREDICT_METHOD_OFFICIAL_STEP = 'official_step'
PREDICT_METHOD_SELF_HOSTED = 'self_hosted_lawgpt'
PREDICT_METHOD_COZE = 'coze_workflow'
PREDICT_METHOD_LANGGRAPH = 'langgraph_workflow'

DEFAULT_PREDICT_PROMPT_TEMPLATE = """
# 最高人民法院裁判文书判决主文撰写提示词
## 模型定位
你是严格遵循中华人民共和国最高人民法院裁判文书制作规范的专业判决主文撰写模型，仅输出“判决如下”之后的正式生效判决主文内容，所有表述与最高人民法院官方发布的生效裁判文书标准文风、句式、格式完全一致，不得输出任何其他无关内容。

## 绝对不可突破的裁判底线规则（零容忍违规即失效）
1. 你只能基于【待预测案情】中“本院认为”部分最终明确的定性结论、对原审各判项的维持/撤销/改判意见撰写判项，**绝对禁止作出任何与本院最终定性相反、超出本院改判范围的判项**。
2. 本院已明确“事实清楚、证据确实充分、定罪准确、量刑适当、应予维持”的所有原审判项，必须100%完整维持，**绝对禁止擅自撤销、改判、调整刑期、变更罪名**。
3. 本院已明确“认定错误、不能成立、应予撤销”的所有原审判项，必须精准对应原审文书全称、案号、具体判项内容完整撤销，**绝对禁止遗漏、错误维持、扩大/缩小撤销范围**。
4. 你只能认定【待预测案情】中本院最终确认成立的罪名，**绝对禁止增设、变更公诉机关未指控、本院未审理确认的任何罪名**，绝对禁止将本院已否定的罪名重新认定成立。
5. 必须完整覆盖本案所有原审审级的生效裁判文书（含一审、二审、指令再审后的再审裁定），针对每一份文书分别明确维持与撤销的具体内容，**绝对禁止遗漏任何一份生效裁判文书的处理**。

## 通用基础规则
1. 严格执行《人民法院刑事裁判文书制作规范》《人民法院民事裁判文书制作规范》《人民法院行政裁判文书制作规范》及最高人民法院发布的官方裁判文书样式，所有表述符合司法实践标准。
2. 仅输出“判决如下”之后的正式判决主文，不得添加前置说理、法条引用、解释说明、总结备注，不得使用分点、列表、序号、特殊格式标记，仅以法院标准的自然段式判项表述，每一项独立成段。
3. 裁判主文逻辑顺序严格遵循法院规范层级：先处理原审裁判文书的维持事项，再处理原审裁判文书的撤销事项，再处理实体改判事项，再处理数罪并罚/责任分担事项，再处理刑期计算/履行期限事项，再处理涉案财物处置/诉讼费用负担事项，再处理申诉/上诉请求的最终处理事项，最后作出终审效力声明（如适用）。
4. 法院名称、案号、当事人姓名、罪名、涉案金额、刑期、原审裁判文书全称、程序性动作（撤销/维持/核准/驳回）必须完全复用原文表述，不得做同义改写、删减或变更，仅可在不改变含义的前提下做符合裁判文书规范的最小句式整理。

## 分案件类型专项规则
### 一、刑事案件（含一审、二审、再审、死刑复核、刑事附带民事案件）
1. 定罪判项需明确被告人姓名、所犯罪名，不得遗漏公诉机关指控且经本院审理确认成立的罪名，不得擅自撤销本院已确认成立的罪名。
2. 量刑判项需对应每个罪名明确主刑刑期、附加刑种类及期限，严格贴合案情中本院已确认的量刑情节，本院已认定量刑适当的，不得擅自调整。
3. 数罪并罚判项严格遵循《中华人民共和国刑法》数罪并罚相关规定，明确总和刑期、决定执行的主刑刑期及附加刑内容，明确附加刑合并执行或分别执行的规则。
4. 刑期计算必须严格执行刑期折抵规定，明确“刑期从判决执行之日起计算。判决执行以前先行羁押的，羁押一日折抵刑期一日”；涉及再审改判、已执行部分刑期的，必须明确扣除已执行刑期，准确计算剩余刑期的起止日期，不得遗漏。
5. 需对应案情明确涉案赃款赃物的追缴、退赔、返还、没收事项，本院已认定错误的财物处置判项必须精准撤销，不得遗漏或错误维持。
6. 刑事附带民事案件需在刑事判项后单独列明附带民事判项，明确赔偿主体、赔偿金额、履行期限、连带责任划分，已履行完毕的需明确确认。
7. 再审案件严格遵循再审不加刑及抗诉例外的相关规定，仅能在本院已明确的改判范围内调整判项，不得擅自加重被告人刑罚或扩大改判范围；涉及案外人申诉的再审案件，必须根据本院对申诉请求的最终评价，明确对申诉请求的支持或驳回内容，不得作出与本院评价相反的处理。
8. 死刑复核案件需明确核准或不核准死刑的判项，对应发回重审或改判内容，符合死刑复核案件文书规范。
9. 终审判决需在末尾明确“本判决为终审判决”，死刑复核案件需明确“本裁定送达后即发生法律效力”。

### 二、民事案件（含一审、二审、再审案件）
1. 二审/再审案件先明确维持原审裁判文书中正确的判项内容，再明确撤销原审裁判文书的全称、案号及对应错误判项内容，精准对应具体判项，不得笼统表述。
2. 实体判项需明确当事人的权利义务、履行内容、履行期限、履行方式，连带责任/按份责任的划分，不得超出当事人诉讼请求范围作出判项。
3. 需明确案件受理费、保全费、鉴定费、公告费等全部诉讼相关费用的负担主体、负担金额/比例，一审、二审诉讼费用分别列明，符合《诉讼费用交纳办法》规定。
4. 驳回起诉/上诉的案件，需明确驳回的对象及对应的起诉/上诉请求，符合文书规范。
5. 终审判决需在末尾明确“本判决为终审判决”。

### 三、行政案件
1. 明确被诉行政行为的维持、撤销、确认违法、无效或责令履行的判项，对应行政赔偿的相关内容。
2. 二审/再审案件先处理原审裁判的维持事项，再处理撤销事项，再作出实体改判判项，明确诉讼费用的负担。
3. 终审判决需在末尾明确“本判决为终审判决”。

## 禁止性规则
1. 禁止使用任何分点、列表、序号、加粗、斜体等非裁判文书标准格式，所有判项均以标准自然段表述，每一项独立成段。
2. 禁止在判决主文中添加任何说理、法条引用、解释说明、备注标注、案情回顾内容，仅输出正式生效的判项内容。
3. 禁止超出给定案情的范围创设事实、变更定性、增减判项，不得违背案情中本院已确认的核心事实与裁判意见。
4. 禁止使用非法院标准的生硬句式、口语化表述，所有表述必须与最高人民法院官方发布的生效裁判文书表述完全一致。
5. 禁止输出“判决如下”字样，仅输出该表述之后的正式判决主文内容。

## 输入内容说明
你将收到以下结构化输入信息，需严格基于输入内容撰写判决主文：
1. 【案件类型】：明确案件的性质（刑事/民事/行政）、审理程序（一审/二审/再审/死刑复核）、是否附带民事诉讼
2. 【待预测案情】：案件的全部审理查明事实、控辩/诉辩双方意见、已确认的量刑/责任情节、原审裁判情况、本院对案件的定性与裁判意见
3. 【核心裁判要求】：需重点遵循的裁判规则与要求（如有）

请先从【待预测案情】中精准提取以下核心信息，再严格遵循所有规则撰写判项：
① 本院最终确认成立的罪名/权利义务认定及对应评价；
② 本院最终确认不成立/错误的罪名/判项及对应评价；
③ 本案所有原审生效裁判文书的全称、案号；
④ 本院对申诉/上诉请求的最终处理意见。

请直接输出符合以上全部规则的判决主文内容，不得输出任何其他无关内容。

【案件类型】
{case_type}

【待预测案情】
{content}

请直接输出判决结果：
""".strip()


def _load_prompt_template_from_baseline_file() -> tuple[str, str]:
    """优先加载评测已采纳的基线提示词，失败时回退到内置模板。"""
    prompt_path = Path(__file__).resolve().parent.parent / 'eval' / 'prompts' / 'v1_baseline.txt'

    try:
        text = prompt_path.read_text(encoding='utf-8').strip()
        if '{case_type}' in text and '{content}' in text:
            return text, 'file'
    except Exception:
        pass

    return DEFAULT_PREDICT_PROMPT_TEMPLATE, 'builtin'


def _is_development_env() -> bool:
    env = (os.getenv('FLASK_ENV') or os.getenv('APP_ENV') or os.getenv('ENV') or '').strip().lower()
    debug = (os.getenv('FLASK_DEBUG') or os.getenv('DEBUG') or '').strip().lower()
    return env in {'dev', 'development', 'local'} or debug in {'1', 'true', 'yes', 'on'}


DEFAULT_PREDICT_PROMPT_TEMPLATE, PROMPT_TEMPLATE_SOURCE = _load_prompt_template_from_baseline_file()

if _is_development_env():
    source_label = '文件模板' if PROMPT_TEMPLATE_SOURCE == 'file' else '内置模板'
    print(f"[PromptTemplate] 本次使用的是{source_label}")


def _create_deepseek_client():
    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL
    )


SENTENCING_REPRIEVE_RULES = """
【量刑专项补充规则】
1. 对刑事案件，必须逐一识别每名被告人、每个罪名对应的主刑、附加刑、是否宣告缓刑、是否为死刑缓期执行、以及是否存在数罪并罚后的“决定执行”刑。
2. 一旦案情中出现“缓刑”“宣告缓刑”“死刑，缓期X年执行”“死刑缓期执行”等表述，输出判项时必须完整写出，绝对禁止只写“死刑”或只写“有期徒刑”而遗漏缓刑/缓期执行信息。
3. 必须严格区分以下量刑结果，不得混淆：
   - 死刑
   - 死刑，缓期X年执行
   - 有期徒刑X年
   - 有期徒刑X年，缓刑X年
   - 拘役/管制及其对应缓刑
4. 若同一被告人存在“分罪量刑”和“决定执行刑”，必须分别判断并准确表达；若决定执行刑带有“缓期执行”或“缓刑”，该信息必须在最终判项中完整保留。
5. 在生成最终判决主文前，请先在内部完成一次量刑核对清单：
   - 被告人姓名
   - 罪名
   - 主刑种类与期限
   - 是否缓刑 / 缓刑期限
   - 是否死缓 / 缓期执行年限
   - 是否决定执行
   然后再输出正式主文，但不要把这份清单直接输出给用户。
6. 如果原文不能支持“立即执行死刑”，但能支持“死刑，缓期执行”，则必须优先保留“缓期执行”表述；如果原文明确宣告缓刑，也必须写明缓刑期限。
""".strip()


def _enhance_prompt_template(prompt_template: str | None, case_type: str | None = None) -> str:
    template = (prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE or '').strip()
    if not template:
        template = DEFAULT_PREDICT_PROMPT_TEMPLATE

    normalized_case_type = (case_type or '').strip()
    is_criminal_case = '刑事' in normalized_case_type or '死刑复核' in template or '刑事案件' in template
    if is_criminal_case and '量刑专项补充规则' not in template:
        template = f"{template}\n\n{SENTENCING_REPRIEVE_RULES}"
    return template


def _deepseek_json_completion(messages, max_tokens: int, temperature: float = 0.2, retries: int = 2):
    """使用 DeepSeek JSON mode 获取结构化输出，失败时保留原有解析兜底。"""
    client = _create_deepseek_client()
    last_error = None
    for _ in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.DEEPSEEK_TIMEOUT,
                response_format={"type": "json_object"}
            )
            raw_text = (response.choices[0].message.content or '').strip()
            if not raw_text:
                last_error = ValueError("empty json content")
                continue
            return _safe_parse_json(raw_text), raw_text
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError("DeepSeek JSON mode 调用失败")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _normalize_name_key(text: str) -> str:
    return re.sub(r"[\s,，。；;：:、\(\)（）《》\"'“”‘’\-]", "", (text or "").strip()).lower()


def _split_content_into_chunks(content: str, max_chars: int = 1200) -> List[str]:
    """按自然段切分长文书，避免一次抽取丢失后半段信息。"""
    text = (content or "").strip()
    if not text:
        return []
    paragraphs = [part.strip() for part in re.split(r'\n{2,}', text) if part.strip()]
    if not paragraphs:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    if not paragraphs:
        return [text[:max_chars]]

    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        for start in range(0, len(paragraph), max_chars):
            segment = paragraph[start:start + max_chars].strip()
            if segment:
                chunks.append(segment)
        current = ""
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _make_evidence_snippet(text: str, query: str, radius: int = 80) -> str:
    base_text = _normalize_space(text)
    if not base_text:
        return ""
    query = (query or "").strip()
    if not query:
        return base_text[: radius * 2]
    idx = base_text.find(query)
    if idx == -1:
        return base_text[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(base_text), idx + len(query) + radius)
    snippet = base_text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(base_text):
        snippet = snippet + "..."
    return snippet


def _build_graph_meta(chunk_count: int, source: str = "llm_chunked_json_v1") -> Dict[str, object]:
    return {
        "version": "chunked-json-v1",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "chunk_count": chunk_count,
        "source": source
    }

def analyze_case_with_api(content):
    """调用DeepSeek API分析案件"""
    try:
        first_line = content.strip().split('\n')[0]
        
        prompt = f"""
        分析案件，返回 json 格式，包含以下字段：
        1. title：必须是类似"张某、李某...案件类别判决书"的格式，第一行"{first_line}"如果是这种格式就保留，否则重新生成
        2. sort：刑事案件/民事案件/行政案件/其他（根据title中的案件类别判断）
        3. summary：800-1000字的详细摘要，必须包含法院名称(court)、涉案人员(persons)、相关法律(laws)、纠纷描述(dispute)、案发地点(location)等关键信息
        4. keywords：5-10个关键词列表
        5. court：审理法院名称
        6. laws：涉及的相关法律条文列表（如["刑法第232条", "民法典第1045条"]）
        7. persons：所有涉案人员列表，每个人员包含角色和姓名（如[{{"role": "上诉人", "name": "张某"}}, {{"role": "被上诉人", "name": "李某"}}]）
        8. dispute：案件纠纷的简要描述
        9. location：案发地点
        
        内容：{content[:2000]}
        """
        
        result, _ = _deepseek_json_completion(
            messages=[
                {"role": "system", "content": "你是一个法律分析助手，必须返回纯 json 对象。title格式必须是'人名...案件类别判决书'。摘要要详细完整，涵盖所有关键信息。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
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

        persons = result.get('persons', [])
        if not isinstance(persons, list):
            persons = []

        laws = result.get('laws', [])
        if not isinstance(laws, list):
            laws = []

        summary = result.get('summary', '')
        if len(summary) < 300:
            summary = summary + " （完整摘要请参考案件详情）"

        return {
            "title": title[:50],
            "sort": sort,
            "summary": summary[:1000],
            "keywords": result.get('keywords', [])[:10],
            "court": result.get('court', '')[:50],
            "laws": laws,
            "persons": persons,
            "dispute": result.get('dispute', '')[:300],
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
            "summary": content[:800] + "...",
            "keywords": [],
            "court": "",
            "laws": [],
            "persons": [],
            "dispute": "",
            "location": ""
        }


def extract_entities_relations(content: str, hints: dict | None = None):
    """调用 DeepSeek 进行分段实体关系抽取，并合并为增强属性图。"""
    try:
        chunks = _split_content_into_chunks(content, max_chars=1200)
        if not chunks:
            return {
                "persons": [],
                "graph": {"nodes": [], "links": []},
                "raw": {},
                "meta": _build_graph_meta(0)
            }

        chunk_results = []
        for chunk_index, chunk_text in enumerate(chunks, start=1):
            chunk_data, raw_text = _extract_graph_from_chunk(
                chunk_text=chunk_text,
                hints=hints,
                chunk_index=chunk_index,
                chunk_count=len(chunks)
            )
            normalized_graph = _normalize_chunk_graph(
                nodes=chunk_data.get('nodes', []),
                links=chunk_data.get('links', []),
                chunk_text=chunk_text,
                chunk_index=chunk_index
            )
            chunk_results.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "raw_text": raw_text,
                "raw_json": chunk_data,
                "graph": normalized_graph
            })

        merged_nodes, merged_links = _merge_chunk_graphs(chunk_results)
        merged_nodes, merged_links = _merge_events_by_time_and_persons(merged_nodes, merged_links)

        raw_payload = {
            "chunk_results": [
                {
                    "chunk_index": item["chunk_index"],
                    "raw_json": item["raw_json"],
                    "raw_text": item["raw_text"]
                }
                for item in chunk_results
            ]
        }
        meta = _build_graph_meta(len(chunks))
        return {
            "persons": [node for node in merged_nodes if node.get('type') == 'person'],
            "graph": {"nodes": merged_nodes, "links": merged_links},
            "raw": raw_payload,
            "meta": meta
        }
    except Exception as e:
        print(f"实体关系抽取失败: {e}")
        return {
            "persons": [],
            "graph": {"nodes": [], "links": []},
            "raw": {},
            "meta": _build_graph_meta(0, source="llm_chunked_json_error")
        }


def _safe_parse_json(raw_text: str):
    """更鲁棒地解析模型返回的 JSON。"""
    if raw_text is None:
        raise ValueError("empty response")
    text = raw_text.strip()
    text = text.replace('```json', '').replace('```', '').strip()
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except Exception:
        pass

    fixed = text
    fixed = re.sub(r'//.*', '', fixed)
    fixed = re.sub(r'/\*.*?\*/', '', fixed, flags=re.S)
    fixed = fixed.replace(': None', ': null').replace(': True', ': true').replace(': False', ': false')
    fixed = fixed.replace(':None', ': null').replace(':True', ': true').replace(':False', ': false')
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except Exception:
        pass

    try:
        data = ast.literal_eval(fixed)
        if isinstance(data, (dict, list)):
            return data
    except Exception:
        pass

    try:
        salvage = _salvage_nodes_links(text)
        if salvage:
            return salvage
    except Exception:
        pass

    return json.loads(text)


def _split_complete_json_objects(array_inner: str) -> List[str]:
    """将数组里的完整 JSON 对象切分出来。"""
    objects = []
    buffer = []
    depth = 0
    in_string = False
    escaped = False
    for char in array_inner:
        buffer.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == '{':
                depth += 1
            elif char == '}':
                depth = max(0, depth - 1)
                if depth == 0:
                    object_text = ''.join(buffer).strip()
                    if object_text.endswith(','):
                        object_text = object_text[:-1]
                    objects.append(object_text)
                    buffer = []
    return objects


def _salvage_nodes_links(text: str):
    """从不完整输出中尽可能提取 nodes 与 links。"""
    stripped = text.replace('```json', '').replace('```', '')

    def grab_array_inner(label: str) -> str:
        match = re.search(rf'"{label}"\s*:\s*\[(.*?)]', stripped, flags=re.S)
        if match:
            return match.group(1)
        label_index = stripped.find(f'"{label}"')
        if label_index == -1:
            return ''
        array_start = stripped.find('[', label_index)
        if array_start == -1:
            return ''
        return stripped[array_start + 1:]

    nodes_inner = grab_array_inner('nodes')
    links_inner = grab_array_inner('links')
    if not nodes_inner and not links_inner:
        raise ValueError("no nodes/links found to salvage")

    node_objects = _split_complete_json_objects(nodes_inner)
    link_objects = _split_complete_json_objects(links_inner)
    nodes = []
    for item in node_objects:
        try:
            nodes.append(json.loads(item))
        except Exception:
            continue
    links = []
    for item in link_objects:
        try:
            links.append(json.loads(item))
        except Exception:
            continue
    return {"nodes": nodes, "links": links}


def _extract_graph_from_chunk(chunk_text: str, hints: dict | None, chunk_index: int, chunk_count: int) -> Tuple[Dict[str, object], str]:
    hints_text = ""
    if hints:
        persons_hint = ", ".join(
            [
                f"{p.get('name', '')}/{p.get('role', '') or '无'}"
                for p in hints.get("persons", [])
                if isinstance(p, dict) and p.get("name")
            ]
        )
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
    任务：对中文法律文书的当前片段做实体与关系抽取，仅返回 json 对象（无任何多余文本）。
    当前片段：第 {chunk_index} / {chunk_count} 段。
    知识图谱设计（请严格遵循）：
    - nodes：节点数组。每个节点形如：
      {{"id":"n1","type":"person|event|time|location","name":"张三/盗窃案发/2024年3月/北京市海淀区","role":"原告|被告|证人|法官|检察官|无","conf":0.92}}
    - links：关系列表。每个关系形如：
      {{"source":"p1","target":"e1","relation":"参与","conf":0.88}}
    要求：
    - 仅抽取本片段中明确提到的事实，保持 json 可解析
    - type 必须是 person、event、time、location 四类之一
    - 优先抽取被告、原告、受害人、关键事件、时间、地点
    - 允许同一案件在不同片段重复出现相同人物或事件，后续会做合并
    - 严格排除审理、判决、裁定、上诉、抗诉、检察等程序性节点和关系
    - 输出字段只允许 nodes 和 links
    {hints_text}
    文书片段：
    {chunk_text}
    """
    return _deepseek_json_completion(
        messages=[
            {"role": "system", "content": "你是信息抽取助手，必须返回纯 json 对象，且顶层仅包含 nodes 与 links 两个字段。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=2200
    )


def _normalize_chunk_graph(nodes, links, chunk_text: str, chunk_index: int):
    """规范化单段图谱，并补充证据、置信度、来源片段信息。"""
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(links, list):
        links = []

    normalized_nodes = []
    seen_ids = set()
    trial_keywords = ['审理', '审判', '判决', '裁定', '开庭', '合议庭', '宣判', '上诉', '抗诉', '公诉', '检察', '审查起诉']
    trial_roles = ['法官', '书记员', '检察官', '公诉人', '审判长', '审判员', '合议庭成员']
    for node in nodes:
        node_id = node.get('id') or node.get('name')
        name = _normalize_space(node.get('name', ''))
        node_type = node.get('type', '')
        role = _normalize_space(node.get('role', ''))
        if not node_id or not name:
            continue
        if node_type not in ('person', 'event', 'time', 'location'):
            if any(k in name for k in ['年', '月', '日', '时']):
                node_type = 'time'
            elif any(k in name for k in ['市', '区', '县', '省', '法院', '路', '街', '镇', '村']):
                node_type = 'location'
            else:
                node_type = 'event'
        if node_type == 'person' and role in trial_roles:
            continue
        if node_type == 'event' and any(k in name for k in trial_keywords):
            continue
        if node_type == 'location' and '法院' in name:
            continue
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        conf = node.get('conf', node.get('confidence', 0.8))
        normalized_nodes.append({
            "id": str(node_id),
            "name": name,
            "type": node_type,
            "role": role,
            "conf": float(conf) if isinstance(conf, (int, float)) else 0.8,
            "confidence": float(conf) if isinstance(conf, (int, float)) else 0.8,
            "normalized_name": _normalize_name_key(name),
            "aliases": [name],
            "source_chunk_ids": [chunk_index],
            "evidence": [_make_evidence_snippet(chunk_text, name)]
        })

    valid_ids = {node["id"] for node in normalized_nodes}
    normalized_links = []
    trial_relation_keywords = ['起诉', '被诉', '宣判', '裁定', '审理', '审判', '上诉', '抗诉', '公诉', '检察']
    for relation in links:
        source = relation.get('source')
        target = relation.get('target')
        label = _normalize_space(relation.get('relation', ''))
        if not (source and target and label):
            continue
        if any(k in label for k in trial_relation_keywords):
            continue
        if source in valid_ids and target in valid_ids:
            conf = relation.get('conf', relation.get('confidence', 0.8))
            normalized_links.append({
                "source": str(source),
                "target": str(target),
                "relation": label,
                "conf": float(conf) if isinstance(conf, (int, float)) else 0.8,
                "confidence": float(conf) if isinstance(conf, (int, float)) else 0.8,
                "source_chunk_ids": [chunk_index],
                "evidence": [_make_evidence_snippet(chunk_text, label or '')]
            })
    return {"nodes": normalized_nodes, "links": normalized_links}


def _merge_chunk_graphs(chunk_results):
    """合并多段抽取结果，做实体消歧并生成最终图谱。"""
    node_store: Dict[str, Dict[str, object]] = {}
    relation_store: Dict[Tuple[str, str, str], Dict[str, object]] = {}
    temp_to_final: Dict[Tuple[int, str], str] = {}

    def build_node_key(node: Dict[str, object]) -> str:
        node_type = str(node.get("type", "event"))
        normalized_name = str(node.get("normalized_name") or _normalize_name_key(str(node.get("name", ""))))
        role = _normalize_name_key(str(node.get("role", ""))) if node_type == 'person' else ""
        return f"{node_type}:{normalized_name}:{role}"

    for item in chunk_results:
        chunk_index = item["chunk_index"]
        graph = item["graph"]
        for node in graph.get("nodes", []):
            node_key = build_node_key(node)
            temp_to_final[(chunk_index, node["id"])] = node_key
            if node_key not in node_store:
                node_store[node_key] = {
                    "key": node_key,
                    "type": node.get("type", "event"),
                    "name": node.get("name", ""),
                    "role": node.get("role", ""),
                    "conf": float(node.get("conf", 0.8)),
                    "confidence": float(node.get("confidence", node.get("conf", 0.8))),
                    "normalized_name": node.get("normalized_name", ""),
                    "aliases": list(dict.fromkeys(node.get("aliases", []) or [node.get("name", "")])),
                    "source_chunk_ids": list(dict.fromkeys(node.get("source_chunk_ids", []) or [chunk_index])),
                    "evidence": [snippet for snippet in node.get("evidence", []) if snippet]
                }
            else:
                stored = node_store[node_key]
                stored["conf"] = max(float(stored.get("conf", 0.8)), float(node.get("conf", 0.8)))
                stored["confidence"] = max(float(stored.get("confidence", 0.8)), float(node.get("confidence", node.get("conf", 0.8))))
                if len(str(node.get("name", ""))) > len(str(stored.get("name", ""))):
                    stored["name"] = node.get("name", stored.get("name", ""))
                stored["aliases"] = list(dict.fromkeys(list(stored.get("aliases", [])) + [alias for alias in node.get("aliases", []) if alias]))
                stored["source_chunk_ids"] = list(dict.fromkeys(list(stored.get("source_chunk_ids", [])) + list(node.get("source_chunk_ids", []))))
                stored["evidence"] = list(dict.fromkeys(list(stored.get("evidence", [])) + [snippet for snippet in node.get("evidence", []) if snippet]))[:3]

        for link in graph.get("links", []):
            source_key = temp_to_final.get((chunk_index, link.get("source")))
            target_key = temp_to_final.get((chunk_index, link.get("target")))
            relation = link.get("relation", "")
            if not source_key or not target_key or not relation or source_key == target_key:
                continue
            relation_key = (source_key, target_key, relation)
            if relation_key not in relation_store:
                relation_store[relation_key] = {
                    "source_key": source_key,
                    "target_key": target_key,
                    "relation": relation,
                    "conf": float(link.get("conf", 0.8)),
                    "confidence": float(link.get("confidence", link.get("conf", 0.8))),
                    "source_chunk_ids": list(dict.fromkeys(link.get("source_chunk_ids", []) or [chunk_index])),
                    "evidence": [snippet for snippet in link.get("evidence", []) if snippet]
                }
            else:
                stored = relation_store[relation_key]
                stored["conf"] = max(float(stored.get("conf", 0.8)), float(link.get("conf", 0.8)))
                stored["confidence"] = max(float(stored.get("confidence", 0.8)), float(link.get("confidence", link.get("conf", 0.8))))
                stored["source_chunk_ids"] = list(dict.fromkeys(list(stored.get("source_chunk_ids", [])) + list(link.get("source_chunk_ids", []))))
                stored["evidence"] = list(dict.fromkeys(list(stored.get("evidence", [])) + [snippet for snippet in link.get("evidence", []) if snippet]))[:3]

    final_id_map = {}
    type_counters = {"person": 0, "event": 0, "time": 0, "location": 0}
    merged_nodes = []
    for node_key, node in node_store.items():
        node_type = str(node.get("type", "event"))
        prefix = {"person": "p", "event": "e", "time": "t", "location": "l"}.get(node_type, "n")
        type_counters[node_type] = type_counters.get(node_type, 0) + 1
        final_id = f"{prefix}{type_counters[node_type]}"
        final_id_map[node_key] = final_id
        merged_nodes.append({
            "id": final_id,
            "name": node.get("name", ""),
            "type": node_type,
            "role": node.get("role", ""),
            "conf": float(node.get("conf", 0.8)),
            "confidence": float(node.get("confidence", node.get("conf", 0.8))),
            "normalized_name": node.get("normalized_name", ""),
            "aliases": node.get("aliases", []),
            "source_chunk_ids": node.get("source_chunk_ids", []),
            "evidence": node.get("evidence", [])
        })

    merged_links = []
    for relation in relation_store.values():
        source_id = final_id_map.get(relation["source_key"])
        target_id = final_id_map.get(relation["target_key"])
        if not source_id or not target_id or source_id == target_id:
            continue
        merged_links.append({
            "source": source_id,
            "target": target_id,
            "relation": relation.get("relation", ""),
            "conf": float(relation.get("conf", 0.8)),
            "confidence": float(relation.get("confidence", relation.get("conf", 0.8))),
            "source_chunk_ids": relation.get("source_chunk_ids", []),
            "evidence": relation.get("evidence", [])
        })

    return merged_nodes, merged_links


def _merge_events_by_time_and_persons(nodes, links):
    """按时间与人物集合合并重复事件节点。"""
    id_to_node = {node["id"]: node for node in nodes}
    neighbors = {}
    for node in nodes:
        neighbors[node["id"]] = set()
    for link in links:
        source = link.get("source")
        target = link.get("target")
        neighbors.setdefault(source, set()).add(target)
        neighbors.setdefault(target, set()).add(source)

    events = [node for node in nodes if node.get("type") == "event"]
    event_groups = {}
    for event in events:
        event_id = event["id"]
        persons = []
        times = []
        for neighbor_id in neighbors.get(event_id, set()):
            neighbor = id_to_node.get(neighbor_id)
            if not neighbor:
                continue
            if neighbor.get("type") == "person":
                persons.append(neighbor["id"])
            elif neighbor.get("type") == "time":
                times.append(neighbor["id"])
        key = (times[0] if times else "", tuple(sorted(set(persons))))
        event_groups.setdefault(key, []).append(event_id)

    remap = {}
    merged_events = {}
    for _, event_ids in event_groups.items():
        if len(event_ids) <= 1:
            continue
        event_nodes = [id_to_node[event_id] for event_id in event_ids if event_id in id_to_node]
        main_event = max(event_nodes, key=lambda item: len(item.get("name", "")))
        merged_name = main_event.get("name", "") or "合并事件"
        if any(node.get("name") != merged_name for node in event_nodes):
            merged_name = f"{merged_name}（合并{len(event_nodes)}）"
        merged_id = event_nodes[0]["id"]
        merged_conf = max([
            node.get("conf", 1.0) if isinstance(node.get("conf", 1.0), (int, float)) else 1.0
            for node in event_nodes
        ] + [1.0])
        merged_confidence = max([
            node.get("confidence", node.get("conf", 1.0)) if isinstance(node.get("confidence", node.get("conf", 1.0)), (int, float)) else 1.0
            for node in event_nodes
        ] + [1.0])
        merged_attrs = event_nodes[0].get("attrs", {}) if isinstance(event_nodes[0].get("attrs", {}), dict) else {}
        merged_aliases = list(dict.fromkeys([alias for node in event_nodes for alias in node.get("aliases", []) if alias]))
        merged_chunk_ids = list(dict.fromkeys([chunk_id for node in event_nodes for chunk_id in node.get("source_chunk_ids", [])]))
        merged_evidence = list(dict.fromkeys([snippet for node in event_nodes for snippet in node.get("evidence", []) if snippet]))[:3]
        normalized_name = _normalize_name_key(main_event.get("name", ""))
        merged_events[merged_id] = {
            "id": merged_id,
            "type": "event",
            "name": merged_name,
            "role": "",
            "conf": float(merged_conf),
            "confidence": float(merged_confidence),
            "attrs": merged_attrs,
            "normalized_name": normalized_name,
            "aliases": merged_aliases or [merged_name],
            "source_chunk_ids": merged_chunk_ids,
            "evidence": merged_evidence
        }
        for event_id in event_ids:
            if event_id != merged_id:
                remap[event_id] = merged_id

    if not remap:
        return nodes, links

    kept_nodes = []
    seen = set()
    for node in nodes:
        node_id = node["id"]
        if node.get("type") == "event" and node_id in remap:
            continue
        if node.get("type") == "event" and node_id in merged_events:
            if node_id in seen:
                continue
            kept_nodes.append(merged_events[node_id])
            seen.add(node_id)
        else:
            kept_nodes.append(node)

    dedup: Dict[Tuple[str, str, str], Dict[str, object]] = {}
    kept_links = []
    for link in links:
        source = remap.get(link.get("source"), link.get("source"))
        target = remap.get(link.get("target"), link.get("target"))
        if source == target:
            continue
        key = (source, target, link.get("relation", ""))
        if key not in dedup:
            dedup[key] = {
                "source": source,
                "target": target,
                "relation": link.get("relation", ""),
                "conf": link.get("conf", 1.0),
                "confidence": link.get("confidence", link.get("conf", 1.0)),
                "source_chunk_ids": list(link.get("source_chunk_ids", [])),
                "evidence": list(link.get("evidence", []))
            }
            continue
        existing = dedup[key]
        existing["conf"] = max(float(existing.get("conf", 1.0)), float(link.get("conf", 1.0)))
        existing["confidence"] = max(float(existing.get("confidence", 1.0)), float(link.get("confidence", link.get("conf", 1.0))))
        existing["source_chunk_ids"] = list(dict.fromkeys(list(existing.get("source_chunk_ids", [])) + list(link.get("source_chunk_ids", []))))
        existing["evidence"] = list(dict.fromkeys(list(existing.get("evidence", [])) + list(link.get("evidence", []))))[:3]

    kept_links = list(dedup.values())

    used = set()
    for link in kept_links:
        used.add(link["source"])
        used.add(link["target"])
    kept_nodes = [node for node in kept_nodes if node["id"] in used or node.get("type") != "event"]
    return kept_nodes, kept_links


def _build_prompt(content, case_type='其他', prompt_template=None):
    template = _enhance_prompt_template(prompt_template, case_type)
    prompt = template.format(
        case_type=case_type or '其他',
        content=content[:3000]
    )
    return template, prompt


def _predict_with_official_step(content, case_type='其他', prompt_template=None):
    """方案1：直连 DeepSeek 官方模型。"""
    try:
        if not content or len(content.strip()) < 20:
            return {
                "prediction": "内容过短，无法进行有效预测。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_OFFICIAL_STEP,
                "success": False
            }

        api_key = settings.DEEPSEEK_API_KEY
        base_url = settings.DEEPSEEK_BASE_URL
        model_name = settings.DEEPSEEK_MODEL
        provider_name = 'DeepSeek'

        if not api_key:
            return {
                "prediction": f"{provider_name} API Key 未配置，请在 .env 中设置对应 KEY。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_OFFICIAL_STEP,
                "success": False
            }

        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        template, prompt = _build_prompt(content, case_type, prompt_template)

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是专业法律助手，输出准确、结构化、可读的中文判决预测分析结果。"},
                {"role": "system", "content": "对刑事案件必须特别识别并保留缓刑、死刑缓期执行、决定执行刑等量刑信息，禁止遗漏“缓刑/缓期执行”表述。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=900,
            timeout=settings.DEEPSEEK_TIMEOUT
        )

        prediction_text = (response.choices[0].message.content or '').strip()
        if not prediction_text:
            prediction_text = "模型未返回预测内容。"

        return {
            "prediction": prediction_text,
            "used_prompt_template": template,
            "method": PREDICT_METHOD_OFFICIAL_STEP,
            "success": True
        }

    except Exception as e:
        print(f"官方模型预测调用失败: {e}")
        error_message = str(e).strip().replace('\n', ' ')
        if len(error_message) > 160:
            error_message = error_message[:160] + '...'
        return {
            "prediction": f"预测失败：{error_message or '请稍后重试'}",
            "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
            "method": PREDICT_METHOD_OFFICIAL_STEP,
            "success": False
        }


def _predict_with_self_hosted(content, case_type='其他', prompt_template=None):
    """方案2：自部署微调模型（LawGPT）预测通道。"""
    try:
        if not content or len(content.strip()) < 20:
            return {
                "prediction": "内容过短，无法进行有效预测。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_SELF_HOSTED,
                "success": False
            }

        model_url = (settings.SELF_HOSTED_MODEL_URL or '').strip()
        if not model_url:
            return {
                "prediction": "自部署模型地址未配置，请在 .env 中设置 SELF_HOSTED_MODEL_URL。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_SELF_HOSTED,
                "success": False
            }

        template, prompt = _build_prompt(content, case_type, prompt_template)

        # 模式A：OpenAI兼容接口（推荐）
        if model_url.endswith('/v1'):
            client = OpenAI(
                api_key=settings.SELF_HOSTED_API_KEY or 'EMPTY',
                base_url=model_url
            )

            response = client.chat.completions.create(
                model=settings.SELF_HOSTED_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是专业法律助手，输出准确、结构化、可读的中文判决预测分析结果。"},
                    {"role": "system", "content": "对刑事案件必须特别识别并保留缓刑、死刑缓期执行、决定执行刑等量刑信息，禁止遗漏“缓刑/缓期执行”表述。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=900,
                timeout=settings.SELF_HOSTED_TIMEOUT
            )

            prediction_text = (response.choices[0].message.content or '').strip()
            if not prediction_text:
                prediction_text = "模型未返回预测内容。"

            return {
                "prediction": prediction_text,
                "used_prompt_template": template,
                "method": PREDICT_METHOD_SELF_HOSTED,
                "success": True
            }

        # 模式B：自定义HTTP接口
        headers = {'Content-Type': 'application/json'}
        if settings.SELF_HOSTED_API_KEY:
            headers['Authorization'] = f"Bearer {settings.SELF_HOSTED_API_KEY}"

        payload = {
            'content': content,
            'case_type': case_type,
            'prompt': prompt,
            'prompt_template': template,
            'model': settings.SELF_HOSTED_MODEL_NAME
        }

        resp = requests.post(
            model_url,
            headers=headers,
            json=payload,
            timeout=settings.SELF_HOSTED_TIMEOUT
        )
        resp.raise_for_status()

        data = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {}
        prediction_text = (
            data.get('prediction')
            or data.get('result')
            or data.get('text')
            or ''
        ).strip()
        if not prediction_text:
            prediction_text = (resp.text or '').strip()[:3000]
        if not prediction_text:
            prediction_text = "自部署模型未返回预测内容。"

        return {
            "prediction": prediction_text,
            "used_prompt_template": template,
            "method": PREDICT_METHOD_SELF_HOSTED,
            "success": True
        }

    except Exception as e:
        print(f"自部署模型预测调用失败: {e}")
        return {
            "prediction": "自部署模型预测暂时失败，请检查服务地址与接口协议。",
            "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
            "method": PREDICT_METHOD_SELF_HOSTED,
            "success": False
        }


def _predict_with_coze(content, case_type='其他', prompt_template=None):
    """方案3：Coze工作流（stream_run SSE）。"""
    try:
        if not content or len(content.strip()) < 20:
            return {
                "prediction": "内容过短，无法进行有效预测。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_COZE,
                "success": False
            }

        workflow_url = (settings.COZE_WORKFLOW_URL or '').strip()
        api_key = (settings.COZE_API_KEY or '').strip()
        project_id = (settings.COZE_PROJECT_ID or '').strip()
        session_id = (settings.COZE_SESSION_ID or '').strip()

        missing = []
        if not workflow_url:
            missing.append('COZE_WORKFLOW_URL')
        if not api_key:
            missing.append('COZE_API_KEY')
        if not project_id:
            missing.append('COZE_PROJECT_ID')
        if not session_id:
            missing.append('COZE_SESSION_ID')

        if missing:
            return {
                "prediction": f"Coze配置缺失：{', '.join(missing)}",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_COZE,
                "success": False
            }

        template, prompt = _build_prompt(content, case_type, prompt_template)

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        }

        payload = {
            'content': {
                'query': {
                    'prompt': [
                        {
                            'type': 'text',
                            'content': {
                                'text': prompt
                            }
                        }
                    ]
                }
            },
            'type': 'query',
            'session_id': session_id,
            'project_id': project_id
        }

        response = requests.post(
            workflow_url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=settings.COZE_TIMEOUT
        )

        if response.status_code >= 400:
            error_text = (response.text or '').strip().replace('\n', ' ')
            if len(error_text) > 200:
                error_text = error_text[:200] + '...'
            return {
                "prediction": f"Coze调用失败（HTTP {response.status_code}）：{error_text or '请检查URL/Token/Project/Session'}",
                "used_prompt_template": template,
                "method": PREDICT_METHOD_COZE,
                "success": False
            }

        def _extract_text(candidate, parent_key=''):
            if isinstance(candidate, str):
                value = candidate.strip()
                if not value:
                    return ''
                if value.isdigit() and len(value) <= 4:
                    return ''
                return value

            if isinstance(candidate, dict):
                preferred_keys = [
                    'answer', 'output', 'final_output', 'text', 'content', 'result'
                ]

                ignored_keys = {
                    'code', 'status', 'status_code', 'event', 'type',
                    'session_id', 'project_id', 'id', 'index'
                }

                for key in preferred_keys:
                    value = candidate.get(key)
                    text = _extract_text(value, key)
                    if text:
                        return text

                for key, value in candidate.items():
                    if key in ignored_keys:
                        continue
                    text = _extract_text(value, key)
                    if text:
                        return text

            if isinstance(candidate, list):
                for item in candidate:
                    text = _extract_text(item, parent_key)
                    if text:
                        return text

            return ''

        chunks = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue

            if not line.startswith('data:'):
                continue

            data_text = line[5:].strip()
            if not data_text or data_text == '[DONE]':
                continue

            try:
                parsed = json.loads(data_text)
                extracted = _extract_text(parsed)
                if extracted:
                    chunks.append(extracted)
            except Exception:
                if data_text:
                    chunks.append(data_text)

        if not chunks:
            return {
                "prediction": "Coze未返回可解析的预测内容。",
                "used_prompt_template": template,
                "method": PREDICT_METHOD_COZE,
                "success": False
            }

        prediction_text = max(chunks, key=len).strip()
        if not prediction_text:
            prediction_text = ''.join(chunks).strip()

        if not prediction_text:
            prediction_text = "Coze未返回有效文本。"

        return {
            "prediction": prediction_text,
            "used_prompt_template": template,
            "method": PREDICT_METHOD_COZE,
            "success": True
        }

    except Exception as e:
        print(f"Coze工作流调用失败: {e}")
        return {
            "prediction": "Coze工作流预测暂时失败，请检查配置与接口协议。",
            "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
            "method": PREDICT_METHOD_COZE,
            "success": False
        }


def _predict_with_langgraph(content, case_type='其他', prompt_template=None):
    """方案4：LangGraph多步工作流预测通道。"""
    try:
        if not content or len(content.strip()) < 20:
            return {
                "prediction": "内容过短，无法进行有效预测。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_LANGGRAPH,
                "success": False
            }

        if not settings.DEEPSEEK_API_KEY:
            return {
                "prediction": "LangGraph通道依赖DEEPSEEK_API_KEY，请先在 .env 中配置。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_LANGGRAPH,
                "success": False
            }

        from .langgraph_pipeline import run_langgraph_prediction

        result = run_langgraph_prediction(
            content=content,
            case_type=case_type,
            prompt_template=prompt_template,
        )

        return {
            "prediction": result.get("prediction", "模型未返回预测内容。"),
            "used_prompt_template": result.get("used_prompt_template", prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE),
            "method": PREDICT_METHOD_LANGGRAPH,
            "success": bool(result.get("success", False))
        }

    except ImportError as e:
        print(f"LangGraph依赖未安装: {e}")
        return {
            "prediction": "LangGraph依赖未安装，请执行 pip install -r requirement.txt 后重试。",
            "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
            "method": PREDICT_METHOD_LANGGRAPH,
            "success": False
        }
    except Exception as e:
        print(f"LangGraph工作流预测调用失败: {e}")
        return {
            "prediction": "LangGraph工作流预测暂时失败，请检查配置与工作流节点逻辑。",
            "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
            "method": PREDICT_METHOD_LANGGRAPH,
            "success": False
        }


def predict_judgement_with_api(content, case_type='其他', prompt_template=None, method=None):
    """统一预测入口：四种方法分发。"""
    method = method or settings.PREDICT_METHOD_DEFAULT

    if method == PREDICT_METHOD_OFFICIAL_STEP:
        return _predict_with_official_step(content, case_type, prompt_template)
    if method == PREDICT_METHOD_SELF_HOSTED:
        return _predict_with_self_hosted(content, case_type, prompt_template)
    if method == PREDICT_METHOD_COZE:
        return _predict_with_coze(content, case_type, prompt_template)
    if method == PREDICT_METHOD_LANGGRAPH:
        return _predict_with_langgraph(content, case_type, prompt_template)

    return {
        "prediction": f"未知预测方法：{method}",
        "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
        "method": method,
        "success": False
    }
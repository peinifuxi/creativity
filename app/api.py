from openai import OpenAI
import json
import requests
import os
from pathlib import Path
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

def analyze_case_with_api(content):
    """调用DeepSeek API分析案件"""
    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,   
            base_url=settings.DEEPSEEK_BASE_URL  
        )
        
        first_line = content.strip().split('\n')[0]
        
        prompt = f"""
        分析案件，返回JSON：
        1. title：必须是类似"张某、李某...案件类别判决书"的格式，第一行"{first_line}"如果是这种格式就保留，否则重新生成
        2. sort：刑事案件/民事案件/行政案件/其他（根据title中的案件类别判断）
        3. summary：500字摘要  # ✅ 这里没问题
        4. keywords：5-10个关键词列表
        
        内容：{content[:1500]}
        """
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个法律分析助手，返回纯JSON。title格式必须是'人名...案件类别判决书'。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000  #
        )
        
        result = json.loads(response.choices[0].message.content.replace('```json', '').replace('```', ''))
        
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
            
        return {
            "title": title[:50],
            "sort": sort,
            "summary": result.get('summary', '')[:500],  
            "keywords": result.get('keywords', [])[:10]
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
            "summary": content[:500] + "...",  
            "keywords": []
        }


def _build_prompt(content, case_type='其他', prompt_template=None):
    template = prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE
    prompt = template.format(
        case_type=case_type or '其他',
        content=content[:3000]
    )
    return template, prompt


def _predict_with_official_step(content, case_type='其他', prompt_template=None):
    """方案1：直连官方现成大模型（硅基流动）。"""
    try:
        if not content or len(content.strip()) < 20:
            return {
                "prediction": "内容过短，无法进行有效预测。",
                "used_prompt_template": prompt_template or DEFAULT_PREDICT_PROMPT_TEMPLATE,
                "method": PREDICT_METHOD_OFFICIAL_STEP,
                "success": False
            }

        api_key = settings.SILICONFLOW_API_KEY
        base_url = settings.SILICONFLOW_BASE_URL
        model_name = settings.SILICONFLOW_MODEL
        provider_name = '硅基流动'

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
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=900,
            timeout=settings.SILICONFLOW_TIMEOUT
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

        if not settings.SILICONFLOW_API_KEY:
            return {
                "prediction": "LangGraph通道依赖SILICONFLOW_API_KEY，请先在 .env 中配置。",
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
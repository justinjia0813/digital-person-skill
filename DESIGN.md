# Digital Person Skill — 产品设计手册

> 把某人的社交媒体内容转化为结构化数据，生成可交互的 AI 数字分身 Skill

## 一、产品定位

**一句话：** 把一个人的思维方式数字化，让 AI 能"像他一样思考"。

**核心价值：**
- 不是"让AI读你的文档"（NotebookLM），而是"让AI变成你"
- 从公开/半公开内容中提取**观点、决策框架、认知风格**，而非简单存储原文
- 输出是一个可直接部署的 Agent Skill，让任何 AI Agent 都能"穿上这个人的灵魂"

**目标用户：**
| 用户 | 场景 |
|------|------|
| 投资人 | 把研究框架和判断体系传给团队/数字分身 |
| 创始人/KOL | 把内容资产变成可交互的 AI 分身 |
| 家族/传承 | 把长辈的智慧和决策经验数字化保留 |
| 咨询顾问 | 把方法论标准化，让 AI 辅助交付 |

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────┐
│                    输入层 (Adapters)                   │
│  公众号 │ 微博 │ X/Twitter │ 小红书 │ 知乎 │ 播客 │ 手动上传  │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                  处理层 (Processors)                   │
│  内容清洗 │ 主题提取 │ 观点抽取 │ 风格分析 │ 知识三元组  │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                   建模层 (Modeler)                     │
│  认知模型 │ 决策模型 │ 知识图谱 │ 人格画像 │ 观点演化  │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                   输出层 (Skill Generator)             │
│  SKILL.md │ 人格文件 │ 知识库 │ 规则引擎 │ RAG 索引   │
└─────────────────────────────────────────────────────┘
```

---

## 三、输入层：数据采集适配器

### 3.1 支持的数据源

| 平台 | 数据类型 | 采集方式 | 难度 |
|------|---------|---------|------|
| 微信公众号 | 文章（长文） | API + 爬虫 | ⭐⭐ |
| 微博 | 短文、长文、评论 | 导出CSV/API | ⭐ |
| X/Twitter | 推文、长推文 | API（免费版有限制） | ⭐⭐ |
| 小红书 | 图文笔记 | 爬虫（反爬强） | ⭐⭐⭐ |
| 知乎 | 回答、文章 | API | ⭐⭐ |
| 播客 | 音频 | Whisper 转写 | ⭐⭐ |
| 手动上传 | PDF/Word/图片/链接 | OCR + 解析 | ⭐ |

### 3.2 统一数据格式

每条内容标准化为：

```json
{
  "id": "wx_20260320_001",
  "source": "wechat_mp",
  "author": "张三",
  "title": "我对AI行业的三个误判",
  "content": "正文...",
  "content_type": "article | short_post | comment | transcript",
  "publish_time": "2026-03-20T10:00:00Z",
  "url": "https://...",
  "metadata": {
    "engagement": {"reads": 5000, "likes": 120, "shares": 30},
    "auto_tags": ["AI", "投资", "行业判断"],
    "sentiment": "reflective | assertive | questioning | humorous",
    "word_count": 3500
  }
}
```

### 3.3 Adapter 接口规范

```python
class BaseAdapter:
    """所有适配器的基类"""
    
    def fetch_profile(self, user_id: str) -> ProfileInfo:
        """获取用户基础信息（昵称、简介、粉丝数等）"""
        raise NotImplementedError
    
    def fetch_content(self, user_id: str, since: str = None, limit: int = 100) -> list[ContentItem]:
        """拉取内容列表，支持时间范围和数量限制"""
        raise NotImplementedError
    
    def normalize(self, raw_data: any) -> list[ContentItem]:
        """将平台原始数据转为统一格式"""
        raise NotImplementedError
```

---

## 四、处理层：结构化提取

### 4.1 内容清洗器 (content_parser)

- HTML → Markdown（保留结构）
- 去除广告、推荐、无关内容
- 提取正文、标题、发布时间
- 图片 OCR（如果图片含文字）
- 短视频字幕提取

### 4.2 主题提取器 (topic_extractor)

用 LLM 从每条内容中提取 2-5 个主题标签：

```json
{
  "content_id": "wx_20260320_001",
  "topics": [
    {"tag": "AI泡沫", "confidence": 0.95},
    {"tag": "算力投资", "confidence": 0.88},
    {"tag": "半导体供应链", "confidence": 0.72}
  ]
}
```

### 4.3 观点提取器 (opinion_extractor) ⭐ 核心

从内容中提取结构化观点：

```json
{
  "opinion_id": "op_001",
  "content_id": "wx_20260320_001",
  "claim": "AI行业存在泡沫，但底层算力投资是合理的",
  "claim_type": "judgment | prediction | advice | critique",
  "reasoning": [
    "数据中心建设数据在减速",
    "物理约束（电力、芯片）不会消失",
    "但模型能力提升是真实的"
  ],
  "evidence_refs": ["Wood Mackenzie报告", "xAI孟菲斯集群数据"],
  "confidence": "high | medium | low",
  "domain": "AI/投资",
  "sentiment": "cautiously_optimistic",
  "time_context": "2026年Q1"
}
```

**观点交叉验证：**
- 同一主题下，他在不同时间的观点是否一致？
- 如果变了，找到转折点和原因
- 标记观点强度演变（弱→强，或强→弱）

### 4.4 风格分析器 (style_analyzer)

```yaml
writing_style:
  tone: "专业但不刻板，偶尔毒舌"
  sentence_structure: "短句为主，喜欢用类比和排比"
  vocabulary:
    level: "专业术语密度中等"
    signature_phrases: ["本质上就是", "一句话", "反过来想"]
  rhetorical_devices:
    - analogy: "高频使用（农田→工厂→AIDC）"
    - contrast: "经常用'不是X，而是Y'句式"
    - enumeration: "喜欢用三段式列举"
```

### 4.5 知识三元组生成器 (knowledge_tripler)

从内容中提取实体关系：

```
(算力, 是, AI的底层依赖)
(数据中心, 受制于, 电力供应)
(芯片供应链, 周期为, 18-24个月)
(张三, 认为, 物理约束不会消失)
```

存储格式：JSON-LD 或 CSV，可导入 Neo4j/NetworkX 做图分析。

---

## 五、建模层：人物画像生成

### 5.1 认知模型 (Cognitive Profile)

```yaml
cognitive_model:
  # 思维风格
  thinking_style:
    primary: "structural_analysis"     # 第一性原理/结构化分析
    secondary: "analogy_driven"        # 类比驱动
    tertiary: "contrarian"             # 逆向思考
  
  # 常用分析框架
  common_frameworks:
    - name: "供需分析"
      frequency: "very_high"
      domains: ["投资", "行业研究"]
    - name: "博弈论"
      frequency: "high"
      domains: ["竞争格局", "谈判"]
    - name: "历史类比"
      frequency: "medium"
      domains: ["技术周期", "市场泡沫"]
  
  # 信息处理偏好
  information_preference:
    trusts: ["一手数据", "学术论文", "内部交流"]
    skeptical_of: ["媒体叙事", "PPT故事", "创始人自述"]
    decision_speed: "medium"           # 快/中/慢
    data_threshold: "high"             # 做判断需要多少数据支撑
  
  # 认知特征（包含偏见，这很重要）
  cognitive_traits:
    - trait: "逆向思维"
      strength: 0.85
      evidence: "多次在市场共识相反方向做判断"
    - trait: "技术乐观但商业审慎"
      strength: 0.75
      evidence: "相信技术但质疑商业化路径"
    - trait: "厌恶PPT叙事"
      strength: 0.90
      evidence: "多次公开表达对融资路演的不信任"
```

### 5.2 决策模型 (Decision Model)

```yaml
decision_model:
  # 决策清单（面对特定场景时的检查项）
  checklists:
    - scenario: "评估一个Pre-IPO投资机会"
      questions:
        - "SEC注册了吗？"
        - "份额来源透明吗？"
        - "退出路径清晰吗？"
        - "定价跟上一轮比涨了多少？"
      typical_outcome: "谨慎，除非有硬数据支撑"
      past_decisions:
        - case: "Jarsy平台评估"
          result: "pass"
          reasoning: "平台太新，退出路径不明"
    
    - scenario: "看到一个AI相关项目"
      questions:
        - "是生产力工具还是融资故事？"
        - "谁来买单？商业模式是什么？"
        - "技术壁垒是什么？能被复现吗？"
      typical_outcome: "区分叙事和实质"
    
    - scenario: "评估一个新材料项目"
      questions:
        - "技术路线成熟度？"
        - "客户验证到什么阶段？"
        - "产能爬坡需要多久？"
      typical_outcome: "看重客户验证和产能进度"

  # 决策模式总结
  patterns:
    - "先证伪，再证实"
    - "重数据，轻叙事"
    - "关注物理约束和供应链"
    - "对早期项目要求更低的估值折扣"
```

### 5.3 知识图谱 (Knowledge Graph)

```json
{
  "nodes": [
    {"id": "AI", "type": "domain", "depth": "expert", "since": "2020"},
    {"id": "Web3", "type": "domain", "depth": "learning", "since": "2025"},
    {"id": "半导体", "type": "domain", "depth": "professional", "since": "2023"},
    {"id": "新能源材料", "type": "domain", "depth": "professional", "since": "2023"},
    {"id": "算力", "type": "concept", "depth": "deep", "since": "2024"},
    {"id": "Token经济", "type": "concept", "depth": "deep", "since": "2025"}
  ],
  "edges": [
    {"from": "算力", "to": "AI", "relation": "is_foundation_of"},
    {"from": "半导体", "to": "算力", "relation": "enables"},
    {"from": "Token经济", "to": "AI", "relation": "measures"}
  ]
}
```

### 5.4 观点演化追踪 (Opinion Evolution)

```yaml
evolution:
  - topic: "AI泡沫"
    timeline:
      - time: "2024-06"
        stance: "有泡沫迹象但不过分担忧"
        source: "微博讨论"
      - time: "2025-03"
        stance: "泡沫确实存在，但底层投资合理"
        source: "公众号文章《我对AI行业的三个误判》"
      - time: "2025-11"
        stance: "需要区分叙事层和应用层"
        source: "Token Economy 第三章"
    trend: "越来越细致，从二元判断→多维度分析"
    triggers: ["实际项目调研增多", "开始写书系统化思考"]
```

---

## 六、输出层：Skill 包生成

### 6.1 目录结构

```
digital-person-{name}/
├── SKILL.md                      # Skill 定义文件（给 Agent 的指令）
├── config.yaml                   # 配置（RAG 参数、检索策略、温度等）
├── profile/
│   ├── soul.md                   # 人格（说话风格、价值观、语气）
│   ├── cognitive.md              # 认知模型（思维框架、分析偏好）
│   ├── decisions.md              # 决策规则（场景→检查清单→典型判断）
│   └── knowledge_graph.json      # 知识图谱
├── knowledge/
│   ├── raw/                      # 原始内容存档（按平台分目录）
│   │   ├── wechat_mp/
│   │   ├── weibo/
│   │   └── x_twitter/
│   ├── processed/                # 结构化处理后
│   │   ├── articles.json         # 文章索引
│   │   ├── opinions.json         # 观点库
│   │   └── triplets.json         # 知识三元组
│   └── vector_db/                # 向量索引（RAG 检索用）
│       ├── metadata.json
│       └── index.faiss           # 或 chroma/lance 索引
├── memory/
│   ├── decisions_log.json        # 决策记录
│   └── evolution.json            # 观点演化记录
└── assets/
    └── avatar.png                # 头像（可选）
```

### 6.2 SKILL.md 模板

```markdown
# Digital Person: {name}

你现在是 {name} 的数字分身。你的任务是像 {name} 一样思考、判断和表达。

## 核心原则

1. **用他的大脑思考** — 遇到问题时，先检索他的观点和决策记录，用他的框架分析
2. **用他的嘴巴说话** — 遵循他的表达风格、用词习惯和语气
3. **不编造** — 如果没有找到他的相关观点，用他的通用框架推理，并说明"这是我基于你的分析框架推断的"
4. **标注来源** — 引用他的原话或原文时，标注出处

## 行为规则

### 回答问题的流程
1. 从 knowledge/vector_db 中检索相关内容（RAG）
2. 检查 decisions.md 中是否有相关的决策清单
3. 用 cognitive.md 中的分析框架组织答案
4. 用 soul.md 中的风格表达

### 风格约束
- {style_constraints}

### 禁止事项
- 不要假装是他本人（明确说明"我是{name}的数字分身"）
- 不要编造他没有表达过的观点
- 不要在敏感话题上代替他表态

## RAG 配置
- 检索模型：{embedding_model}
- 相似度阈值：0.75
- 最大检索片段数：5
- 优先级：观点库 > 决策记录 > 原始文章 > 通用框架
```

### 6.3 config.yaml

```yaml
person:
  name: "张三"
  version: "1.0.0"
  created_at: "2026-04-02"
  data_sources:
    - platform: "wechat_mp"
      article_count: 45
      date_range: "2024-01 to 2026-03"
    - platform: "x_twitter"
      post_count: 230
      date_range: "2023-06 to 2026-03"
  data_quality_score: 0.82  # 综合数据质量评分

rag:
  embedding_model: "text-embedding-3-small"
  similarity_threshold: 0.75
  max_chunks: 5
  chunk_size: 500
  chunk_overlap: 50
  priority_order:
    - opinions       # 观点库最优先
    - decisions      # 决策记录次之
    - articles       # 原始文章再次
    - cognitive      # 通用框架兜底

generation:
  temperature: 0.7
  max_tokens: 2000
  system_prompt_file: "profile/soul.md"
```

---

## 七、渐进式画像

数据量决定画像精度，产品应体现这个渐进过程：

| 阶段 | 数据量 | 画像能力 | 置信度 |
|------|--------|---------|--------|
| L1 雏形 | 5-20 篇文章 | 能模仿说话风格和通用立场 | 30% |
| L2 基础 | 20-100 篇 | 能复制主要思维框架 | 50% |
| L3 成熟 | 100-500 篇 | 能预测他在新场景下的判断 | 70% |
| L4 精确 | 500+ 篇 + 对话记录 | 接近本人的分析能力 | 85% |
| L5 完整 | 全量数据 + 实时更新 | 高保真数字分身 | 95% |

**实现方式：** 每次新数据导入后重新运行建模层，更新画像文件，记录版本变化。

---

## 八、版本控制与演化

### 8.1 画像版本管理

```
versions/
├── v1.0.0/
│   └── profile/          # 2026-04-02 初始版本，45篇文章
├── v1.1.0/
│   └── profile/          # 2026-05-15 新增30篇微博，观点更新
└── CHANGELOG.md          # 版本变化记录
```

### 8.2 演化检测

每次数据更新后，自动检测：
- **新增观点：** 以前没表达过的立场
- **观点变化：** 同一话题上立场发生转变
- **框架演进：** 分析框架变得更精细或发生变化
- **兴趣迁移：** 关注的话题领域发生变化

---

## 九、隐私与安全

### 9.1 数据分级

| 级别 | 数据类型 | 存储方式 | 是否可导出 |
|------|---------|---------|-----------|
| L1 公开 | 公众号、X、公开微博 | 明文存储 | ✅ |
| L2 半公开 | 朋友圈、仅粉丝可见内容 | 加密存储，需授权 | ⚠️ 需确认 |
| L3 私密 | 微信聊天、内部文档 | 端到端加密 | ❌ 仅本地 |

### 9.2 安全措施

- 所有数据本地处理，不上传第三方
- L2/L3 数据使用 AES-256 加密
- 生成的 Skill 包不包含原始私密数据
- 用户可随时删除某个数据源或某段时间的数据
- 生成的分身明确标注"非本人"，避免冒充

---

## 十、技术栈建议

| 层级 | 推荐方案 |
|------|---------|
| 数据采集 | Python + Playwright（反爬强的平台）+ API（有开放API的平台） |
| 内容解析 | readability + html2text + unstructured |
| LLM 处理 | OpenAI GPT-4o / Claude Sonnet（观点提取需要强推理能力） |
| 向量数据库 | LanceDB / Chroma（轻量本地）或 Pinecone（云端） |
| 知识图谱 | NetworkX（轻量）或 Neo4j（重量级） |
| Skill 输出 | Markdown + YAML + JSON（通用格式，兼容 OpenClaw/Claude/任何Agent框架） |
| 前端（可选） | Streamlit / Next.js（数据导入管理面板） |

---

## 十一、MVP 路径

**第一版（2周）：**
1. 公众号文章采集适配器
2. 基础内容清洗 + 主题提取
3. 观点提取器（LLM 调用）
4. 生成 SOUL.md + opinions.json
5. 输出为 OpenClaw Skill 包

**第二版（4周）：**
1. 新增微博、X 适配器
2. 决策框架提取
3. 知识图谱生成
4. RAG 向量索引
5. Skill 包接入 OpenClaw 实测

**第三版（6周+）：**
1. 观点演化追踪
2. 版本控制
3. 前端管理面板
4. 支持导出为 Claude/ChatGPT Custom Instructions 格式
5. 隐私分级管理

---

## 十二、与竞品的差异

| 维度 | NotebookLM | Character.ai | 本产品 |
|------|------------|--------------|--------|
| 定位 | 读你的文档 | 角色扮演聊天 | 数字化思维方式 |
| 输入 | 手动上传文档 | 手动描述角色 | 自动采集社交媒体 |
| 提取 | 全文索引 | 无 | 结构化观点+决策框架 |
| 输出 | 对话助手 | 聊天机器人 | 可部署的 Agent Skill |
| 核心价值 | 信息检索 | 娱乐 | 决策能力复用 |

---

*版本：v0.1.0 | 日期：2026-04-02 | 作者：Jared 🦞*

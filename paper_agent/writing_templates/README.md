# writing_templates

各研究领域目录下的 `writing_templates/` 存放**参考论文的写作风格模板**，供 Paper Agent 在生成 LaTeX 章节时注入 LLM Prompt，引导模型模仿学术论文的结构、语气与表述方式。

```
paper_agent/{field}/writing_templates/
├── abstract/
├── introduction/
├── methodology/
├── related_work/
├── experiments/
├── conclusion/
└── preliminaries/
```

其中 `{field}` 为 `vq` | `gnn` | `rec` | `diffu_flow`。

---

## 这是 RAG 吗？

**不完全是。** 你的理解「把若干篇参考论文按章节切分」是对的，但用法更接近 **Few-shot 写作范例（Style Template）**，而不是向量检索式 RAG：

| 对比项 | 本项目的 writing_templates | 典型 RAG |
|--------|---------------------------|----------|
| 选取方式 | `random.choice()` **随机**选一篇同章节模板 | 按语义相似度检索 Top-K |
| 存储形式 | 纯文本 `.txt`，无 embedding | 向量库 + 元数据 |
| 内容形态 | 原文**泛化**为带占位符的骨架（如 `[Method Name]`） | 通常保留原文片段 |
| 注入时机 | 写入 Prompt 的 `REFERENCE WRITING TEMPLATE` 段 | 作为检索上下文拼入 Prompt |
| 事实来源 | **不是**模板；真实内容来自 Agent JSON、代码、benchmark | 检索文档即知识来源 |

实际流程：

```
研究产出（代码 / Agent 日志 / benchmark）
        ↓  作为主要写作素材
detailize_subsection() 构造 Prompt
        ↓
随机读取 writing_templates/{section}/*.txt 作为风格参考
        ↓
GPTClient.chat() 生成 LaTeX
```

代码入口见 [`section_composer.py`](../section_composer.py) 的 `get_random_template()`，在 `detailize_subsection` 中被各章节 Composer 调用。

---

## 各子目录作用

每个子目录对应论文的一个**章节类型**。目录内每个文件是一篇参考论文在该章节上的**写作骨架模板**。

命名规则：

```
{paper_title_normalized}_{section}_template.txt
```

示例：

```
maskgit:_masked_generative_image_transformer_abstract_template.txt
neural_discrete_representation_learning_methodology_template.txt
```

### `abstract/`

**用途：** 摘要写作范例——Problem Context → Proposed Solution → Results & Impact 的段落组织与学术表述。

**被谁使用：** [`abstract_composing.py`](../abstract_composing.py)（`section_name="abstract"`）

**模板特点：** 多为 `\begin{abstract}...\end{abstract}` 结构，强调简洁、无引用、单段或短段。

---

### `introduction/`

**用途：** 引言写作范例——背景、动机、方法概览、贡献列表的叙述顺序与过渡方式。

**被谁使用：** [`introduction_composing.py`](../introduction_composing.py)

**模板特点：** 高层次叙述，不含复杂公式；展示如何引出问题、对比现有方法、预告本文贡献。

---

### `methodology/`

**用途：** 方法章节写作范例——组件划分、公式呈现、符号定义、模块间数据流的写法。

**被谁使用：** [`methodology_composing_using_template.py`](../methodology_composing_using_template.py)

**模板特点：** 含 `\section` / `\subsection`、`\begin{equation}`、figure 占位等，是**技术深度**的主要参考来源。

---

### `related_work/`

**用途：** 相关工作写作范例——按研究方向分组、引用对比、指出现有不足并过渡到本文的写法。

**被谁使用：** [`related_work_composing_using_template.py`](../related_work_composing_using_template.py)

**模板特点：** 展示 `\section{Related Work}` 下多个 `\subsection` 的组织方式，以及「某工作做了 X，然而存在 Y 局限」的对比句式。

> Related Work 的**事实内容**主要来自 `survey_agent.json` 与 `workplace/papers/` 中的 arXiv TeX，模板只提供行文风格。

---

### `experiments/`

**用途：** 实验章节写作范例——Experimental Settings、主结果、消融实验、表格与指标描述的写法。

**被谁使用：** [`experiments_composing.py`](../experiments_composing.py)

**模板特点：** 含数据集/基线/实现细节子节结构，以及如何嵌入结果表格与分析的表述模式。

> 实验的**真实数值**来自 `experiment_analysis_agent_*.json` 与 `workplace/project/` 代码，而非模板。

---

### `conclusion/`

**用途：** 结论写作范例——总结贡献、呼应引言动机、适度展望的短段落写法。

**被谁使用：** [`conclusion_composing.py`](../conclusion_composing.py)

**模板特点：** 通常 1 段，无新信息，强调与 Introduction / Experiments 的呼应。

---

### `preliminaries/`

**用途：** 预备知识 / 符号定义章节的写作范例（如符号表、问题形式化、基础概念回顾）。

**被谁使用：** **当前流水线未使用。** 没有任何 Composer 的 `section_name` 设为 `preliminaries`，`get_random_template()` 不会读取此目录。

**说明：** 这些文件可能是预留扩展，或从完整论文拆分时的副产品。部分 `methodology/` 模板内已内嵌 `\label{sec:preliminaries}` 小节，但独立 `preliminaries/` 目录暂未接入生成流程。

---

## 各领域的参考论文数量

同一篇参考论文在每个**已使用的**章节目录下各有一份模板（`preliminaries` 同样按篇拆分，但未参与生成）。

| 领域目录 | 参考论文数（约） | 说明 |
|----------|-----------------|------|
| `vq/` | **11** | 向量量化、生成模型相关 |
| `diffu_flow/` | **11** | 扩散 / 流匹配相关 |
| `gnn/` | **27** | 图神经网络相关 |
| `rec/` | **31** | 推荐系统相关（对应 benchmark 目录 `recommendation`） |

以 `vq/` 为例，11 篇参考论文为：

1. BERT Pretraining of Video Transformers (bevt)
2. End-to-End Optimized Image Compression
3. Estimating or Propagating Gradients Through Stochastic Neurons
4. InfoGAN
5. Language Models are Few-Shot Learners
6. MaskGIT
7. Neural Discrete Representation Learning (VQ-VAE)
8. SDXL
9. Taming Transformers for High-Resolution Image Synthesis
10. Vector-Quantized Image Modeling with Improved VQGAN
11. Wasserstein GAN

---

## 模板内容长什么样？

模板不是论文原文复制，而是**脱敏后的写作骨架**，用占位符替代具体方法名、公式和结论，例如：

```latex
\section{Optimization of [Model/Method Name]}

Our objective is to minimize [objective function], over the parameters of
[parameters involved], where [explain any relevant terms]. Instead of
[previous method/approach], we [describe the approach taken]...
```

LLM Prompt 中明确说明模板**仅供参考**：

- 学习：段落组织、公式引入方式、学术语气
- 禁止：逐字照搬、强行套用特定格式
- 正文内容：必须来自当前研究的代码与 Agent 输出

---

## 文件是如何组织成「按章节划分」的？

可以把它理解为一个简单的二维表：

```
                    abstract  intro  method  related  exp  conclusion  prelim
Paper A               ✓        ✓       ✓        ✓      ✓       ✓          ✓
Paper B               ✓        ✓       ✓        ✓      ✓       ✓          ✓
...
Paper N               ✓        ✓       ✓        ✓      ✓       ✓          ✓
```

- **行** = 一篇参考论文（同一 `paper_title` 前缀）
- **列** = 论文章节类型
- 生成某一章节时，只从**对应列**随机取一个文件，不会跨章节检索

因此：**是按章节划分的多篇参考论文，但不是按语义检索的 RAG 知识库。**

---

## 如何新增或修改模板

1. 在 `paper_agent/{field}/writing_templates/{section}/` 下新增 `{title}_{section}_template.txt`
2. 文件名必须以 `_template.txt` 结尾（`get_random_template()` 的过滤条件）
3. 建议保持占位符风格，避免写入特定论文的可识别结论
4. 若新增章节类型，需同步实现对应 Composer 并在 `writing.py` 中编排

---

## 相关代码

| 文件 | 作用 |
|------|------|
| [`section_composer.py`](../section_composer.py) | `get_random_template()` 随机读取模板 |
| [`methodology_composing_using_template.py`](../methodology_composing_using_template.py) | Methodology 使用模板 |
| [`related_work_composing_using_template.py`](../related_work_composing_using_template.py) | Related Work 使用模板 |
| [`experiments_composing.py`](../experiments_composing.py) | Experiments 使用模板 |
| [`introduction_composing.py`](../introduction_composing.py) | Introduction 使用模板 |
| [`conclusion_composing.py`](../conclusion_composing.py) | Conclusion 使用模板 |
| [`abstract_composing.py`](../abstract_composing.py) | Abstract 使用模板 |

更多流水线说明见 [`paper_agent/README.md`](../README.md)。

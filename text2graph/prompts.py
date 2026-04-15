prompt_template_weibo = """
你是一个信息抽取系统，需要从微博文本中抽取实体和关系（三元组）。

---

### 一、任务

1. 抽取实体（带类型）
2. 抽取三元组

---

### 二、实体类型
- USER（用户）
- PERSON（人物）
- ORGANIZATION（机构/组织）
- EVENT（事件）
- PRODUCT（产品/工具）
- TOPIC（话题）
- OTHER

---

### 三、关系类型（只能选这些）
- 发布
- 评论
- 回复
- 转发
- 提及
- 使用
- 讨论

---

### 四、抽取规则

-1. “用户xxx” 和“@xxx”→ USER就是xxx
-2. “发布内容” → 发布
-3. “评论了” → 评论
-4. “回复” → 回复
-5. “转发微博” → 转发
-6. 不要编造关系
-7. 三元组必须来自文本
-8. 实体规范化规则
（1）. 以下所有表达必须统一为同一个实体：
   - OpenClaw
   - openclaw
   - openclaw龙虾
   - 小龙虾
   - 龙虾（当指AI工具时）
   - “龙虾”（OpenClaw）

（2）. 抽取时要求：

- 必须保留原始文本中的实体表达，例如：
  - “龙虾”
  - “ClawBot”
  - “OpenClaw”

- 同时需要在语义上识别它们属于同一个产品

（3）. 在 triplets 中：

- 可以统一使用 "OpenClaw" 作为标准实体
- 但在 entities 中必须保留原始出现的名称

例如：
entities:
- OpenClaw
- 龙虾
- ClawBot

triplets:
- ["微信", "接入", "OpenClaw"]

-9. 人名规范化规则
如果一个人名带有修饰词或称号，例如：
   - “红衣大叔周鸿祎”
   - “雷军大佬”
   - “马斯克老板”

必须拆分为：
- 标准人名实体（如上述例子分别拆分为：周鸿祎、雷军、马斯克）
- 修饰词不作为独立实体

---

### 五、示例1（发布+评论）

输入：
用户张三发布内容：OpenClaw很好用。
用户李四评论了张三发布的内容：确实不错。

输出：
{
    "entities": [
        {"name": "张三", "type": "USER"},
        {"name": "李四", "type": "USER"},
        {"name": "OpenClaw", "type": "PRODUCT"}
    ],
    "triplets": [
        ["张三", "发布", "OpenClaw"],
        ["李四", "评论", "张三"]
    ]
}

---

### 示例2（发布+转发）

输入：
用户张三发布了内容：OpenClaw很好用
用户王五转发微博

输出：
{
    "entities": [
        {"name": "张三", "type": "USER"},
        {"name": "王五", "type": "USER"}
    ],
    "triplets": [
        ["王五", "转发", "张三"]
    ]
}

---

### 示例3（回复）

输入：
用户张三对李四进行了回复

输出：
{
    "entities": [
        {"name": "张三", "type": "USER"},
        {"name": "李四", "type": "USER"}
    ],
    "triplets": [
        ["张三", "回复", "李四"]
    ]
}

---

### 示例4（复杂微博）

输入：
用户A发布内容：OpenClaw是一个AI工具。
用户B评论了A发布的内容：确实很强。
用户C转发微博
用户D：openclaw有没有风险？
用户E转发了用户D的评论。


输出：
{
    "entities": [
        {"name": "A", "type": "USER"},
        {"name": "B", "type": "USER"},
        {"name": "C", "type": "USER"},
        {"name": "D", "type": "USER"},
        {"name": "E", "type": "USER"},
        {"name": "OpenClaw", "type": "PRODUCT"}
    ],
    "triplets": [
        ["A", "发布", "OpenClaw"],
        ["B", "评论", "A"],
        ["C", "转发", "A"],
        ["D", "评论", "A"],
        ["E", "转发", "D"]
    ]
}


### 示例5

输入：
用户A :C说的对吗//@B:没问题//@C:openclaw是工具



输出：
{
    "entities": [
        {"name": "A", "type": "USER"},
        {"name": "B", "type": "USER"},
        {"name": "C", "type": "USER"}
    ],
    "triplets": [
        ["B", "转发", "C"],
        ["A", "转发", "B"],
        ["A", "提及", "C"]
    ]
}
---

### 六、待处理文本

{context}

---

请输出JSON结果：
"""
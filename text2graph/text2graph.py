import re
from typing import Dict, Any, List
from tqdm import tqdm
import datetime
import json
import os
import time


# 这是俩大模型后端，openai这个包可以用几乎所有的在线api。ollama可以支持大模型本地部署，也可以用llama_index来本地部署大模型
from openai import OpenAI
# import ollama

EMBEDD_DIMS = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-small-en-v1.5": 384
}

#利用日志进行处理时间记录，包括api调用和本地处理时间
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("run.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def file_exist(path):
    return os.path.exists(path)

def extract_json_from_response(text: str):
    """
    从任意模型输出中提取第一个有效 JSON 对象。
    自动忽略 <think>、``` 等格式。
    """
    cleaned = text.strip()

    # remove markdown mark
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|```$", "", cleaned, flags=re.MULTILINE).strip()

    # match {} content
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if not match:
        raise ValueError(f"❌ 未找到 JSON 内容，原始响应:\n{cleaned}")

    json_str = match.group(0)

    # parse json
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ JSON 解析失败: {e}\n提取内容:\n{json_str}")

def extract_json_str(text: str) -> str:
    """Extract JSON string from text."""
    # NOTE: this regex parsing is taken from langchain.output_parsers.pydantic
    match = re.search(r"\{.*\}", text.strip(), re.MULTILINE | re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract json string from output: {text}")
    return match.group()

class LLM_base:
    def __init__(self, model_name):
        self.model_name = model_name

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
                        api_key = "XXX",
                        base_url="https://api.longcat.chat/openai",#"https://api.deepseek.com",
                    )
        # 跑本地模型
        # self.client = OpenAI(
        #                 api_key="ollama",
        #                 base_url="",
        #             )

        print(self.chat_with_ai("who are you?"))

    def chat_with_ai(self, query):

        messages = [
            {"role": "system", "content": "Please follow the user's instructions carefully."},
            {"role": "user", "content": query}
        ]

        response = self.client.chat.completions.create(
            model=self.model_name,
            # model="llama3.1-8b-instruct",
            # model="llama3:8b-instruct-fp16", # local model
            # model="Meta-Llama-3.1-8B-Instruct", # local model
            messages=messages,
        )
        return response


from prompts import prompt_template_weibo

class Text2Graph:
    def __init__(self, file_path: str, graph_name: str, llm_name: str):
        """
        初始化文本到图转换器
        
        Args:
            file_path: 输入的文本文件路径
        """
        self.file_path = file_path
        self.graph_name = graph_name

        if not file_exist(self.file_path):
            raise FileNotFoundError(f"文本文件未找到: {self.file_path}")
        
        text = self.read_file_path()

        self.text_chunks = self.split_weibo_chunks(text)

        print(f"按微博传播块切分完成，共 {len(self.text_chunks)} 个chunk")

        self.llm = LLM_base(model_name = llm_name)

        #计时
        import time

        self.total_api_time = 0.0
        self.total_local_time = 0.0
        self.start_time = time.perf_counter()

        logger.info("Text2Graph 初始化完成")
    
    def split_weibo_chunks(self, text: str):
        """
        按 '-----' 分割微博传播块
        """
        #按分隔线切分
        raw_chunks = re.split(r'--------------------------------------------------', text)

        chunks = []
        for chunk in raw_chunks:
            chunk = chunk.strip()

            chunks.append(chunk)

        return chunks


    def llm_extract(self, context):
        output = None
        retry = 3
        while retry > 0:
            try:
                output = self.llm.chat_with_ai(prompt_template_weibo.format(context=context))
                output = extract_json_str(output)
                parsed_output = json.loads(output)
                assert "entities" in parsed_output and "triplets" in parsed_output
                return parsed_output
            except Exception as e:
                print(f"JSON format error: {e}")
                retry -= 1  # Decrement the retry counter
        return output

    def read_file_path(self) -> str:
        import os
        ext = os.path.splitext(self.file_path)[1].lower()
        text = ""

        if ext == ".txt":
            with open(self.file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        elif ext == ".docx":
            from docx import Document
            doc = Document(self.file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        
        elif ext == ".doc":
            import mammoth
            with open(self.file_path, "rb") as f:
                result = mammoth.extract_raw_text(f)
                text = result.value
        
        elif ext == ".pdf":
            import fitz  # PyMuPDF
            # 打开 PDF
            doc = fitz.open(self.file_path)
            # 提取每页文本
            text_list = []
            for page in doc:
                page_text = page.get_text("text")  # 按文本顺序提取
                if page_text:  # 有文字才保留
                    text_list.append(page_text)
            # 拼接所有页
            text = "\n".join(text_list)
            # 清理多余空白和换行，保证句子连续
            text = re.sub(r'\r\n|\r', '\n', text)          # 统一换行
            text = re.sub(r'\n+', '\n', text)             # 多个换行合并为一个
            text = re.sub(r'[ \t]+', ' ', text)           # 多空格缩成一个空格
            text = text.strip()                            # 去掉首尾空白
        
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

        return text
        
    def read_file_path_markitdown(self) -> str:
        """
        将用户上传的文件转为 Markdown，并在 schema YAML 中追加一条 text dataset。
        """
        import os
        base_path, _ = os.path.splitext(self.file_path)
        self.md_file_path = f"{base_path}.md"

        # 1️⃣ 转成 Markdown
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(self.file_path)
        markdown_text = result.text_content

        # 2️⃣ 保存 Markdown 文件
        with open(self.md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        return markdown_text
    
    def extract_graph(self, MAX_RETRIES = 5):
        """
        从文本数据中提取知识图谱
        
        Returns:
            三元组列表
        """
        print("开始从文本中提取知识图谱...")
        logger.info(f"开始提取知识图谱，共 {len(self.text_chunks)} 个 chunk")
        
        triplets = []
        entities = []

        for idx, chunk in enumerate(tqdm(self.text_chunks)):
            
            for attempt in range(1, MAX_RETRIES + 1):
                api_start = time.perf_counter()
                #response = self.llm.generate_response(query=prompt_template_str.format(context=chunk))
                response = self.llm.chat_with_ai(query=prompt_template_weibo.replace("{context}", chunk))

                api_end = time.perf_counter()
                cost = api_end - api_start

                self.total_api_time += cost

                logger.info(f"Chunk {idx} API耗时: {cost:.2f}s")
                # 判空
                if not response:
                    print(f"⚠️ 块 {idx} 第 {attempt} 次尝试未获得响应")
                    continue

                local_start = time.perf_counter()

                # 尝试解析 JSON
                response_text = response.choices[0].message.content
                response_parsed = extract_json_from_response(response_text)
                #response_parsed = extract_json_from_response(response)

                local_end = time.perf_counter()
                cost = local_end - local_start

                self.total_local_time += cost

                logger.info(f"Chunk {idx} 本地处理耗时: {cost:.4f}s")

                if isinstance(response_parsed, str):
                    print(f"⚠️ 块 {idx} 第 {attempt} 次响应解析失败")
                    continue

                # 成功获取合法响应，跳出重试循环
                response = response_parsed


                break
            else:
                # 5 次都不成功，跳过该块
                print(f"❌ 块 {idx} 超过 {MAX_RETRIES} 次尝试仍失败，跳过")
                continue

            new_triplets = []

            for triplet in response.get("triplets", []):
                # 1️⃣ 必须是列表/元组且长度为3
                if not isinstance(triplet, (list, tuple)) or len(triplet) != 3:
                    print(f"⚠️ 无效三元组，跳过: {triplet}")
                    continue
                
                # 2️⃣ 遍历每个元素，处理字符串大小写
                processed_triplet = []
                for phrase in triplet:
                    if isinstance(phrase, str) and phrase.strip():
                        processed_triplet.append(phrase.strip().capitalize())
                    else:
                        processed_triplet.append(phrase)  # 保留原样（可能是数字或空）
                
                new_triplets.append(processed_triplet)

            triplets.extend(new_triplets)

        print(f"提取完成，共获得 {len(triplets)} 个三元组。")
        return triplets

    def save_triplet(self, triplets: List[List[str]]):
        import os, csv
        dir_path = os.path.dirname(self.file_path)
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        entities_csv_path = os.path.join(dir_path, f"{base_name}_entity.csv")
        triplets_csv_path = os.path.join(dir_path, f"{base_name}_triplets.csv")
        
        valid_triplets = []
        for t in triplets:
            if len(t) != 3:
                print(f"⚠️ 无效三元组，跳过: {t}")
                continue
            head, rel, tail = t
            if not head or not tail or not rel:
                print(f"⚠️ 三元组元素为空，跳过: {t}")
                continue
            valid_triplets.append([head, rel, tail])

        if not valid_triplets:
            print("⚠️ 没有合法三元组，退出。")
            return

        entities = {}
        next_id = 1
        for head, rel, tail in valid_triplets:
            for ent in [head, tail]:
                if ent not in entities:
                    entities[ent] = next_id
                    next_id += 1

        with open(entities_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["acct_id", "dsply_nm"])
            for ent, eid in entities.items():
                writer.writerow([eid, ent])

        with open(triplets_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["tran_id", "orig_acct", "bene_acct"])
            for head, rel, tail in valid_triplets:
                writer.writerow([entities[head], entities[tail], rel])

        print(f"✅ 实体 CSV 保存到: {entities_csv_path}")
        print(f"✅ 边 CSV 保存到: {triplets_csv_path}")



if __name__ == '__main__':
    text_2_graph = Text2Graph(
        file_path="D:/XXX/text.txt",
        graph_name='example',
        llm_name='LongCat-Flash-Lite'#'deepseek-chat'
    )
    
    triplets =  text_2_graph.extract_graph()
    text_2_graph.save_triplet(triplets)

    end_time = time.perf_counter()
    total_time = end_time - text_2_graph.start_time

    logger.info("========== 性能统计 ==========")
    logger.info(f"总时间: {total_time:.2f}s")
    logger.info(f"API时间: {text_2_graph.total_api_time:.2f}s")
    logger.info(f"本地时间: {text_2_graph.total_local_time:.2f}s")

    if total_time > 0:
        logger.info(f"API占比: {text_2_graph.total_api_time / total_time:.2%}")
        logger.info(f"本地占比: {text_2_graph.total_local_time / total_time:.2%}")

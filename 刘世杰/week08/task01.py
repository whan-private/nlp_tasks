class Text(BaseModel):
    """文本翻译智能体"""
    original_language: List[str] = Field(description="原始语种")
    target_language: List[str] = Field(description="目标语种")
    text_to_be_translated: List[str] = Field(description="待翻译文本")
result = ExtractionAgent(model_name = "qwen-plus").call('帮我把"love me love my dog"翻译成中文', Text)
print(result)

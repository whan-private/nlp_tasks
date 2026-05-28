# 评测体系说明

## 评估维度

### 1. 结果指标
- **胜率**: 各阵营获胜比例（目标：村民 55-65%）
- **存活轮数**: 玩家平均存活轮数
- **击杀效率**: 狼人每轮击杀成功率

### 2. 过程指标
- **推理准确性**: Agent 推理与实际身份的匹配度
- **投票正确率**: 村民投票给狼人的准确率
- **身份隐藏度**: 狼人成功隐藏身份的轮数
- **发言质量**: 基于 LLM 评估的发言逻辑性

### 3. 协作指标
- **狼人协作度**: 狼人团队击杀目标一致性
- **信息共享效率**: 预言家信息传递效果
- **阵营配合度**: 同阵营玩家投票一致性

## 综合评分算法

```
综合分 = 50 + (村民胜利 ? 20 : 0) + 预言家准确率 × 15 + 村民投票准确率 × 15
```

分数范围：0-100

## API 使用

```bash
# 单局报告
curl http://localhost:8000/api/evaluation/{game_id}/report

# 排行榜
curl http://localhost:8000/api/evaluation/leaderboard?limit=20

# 多局对比
curl -X POST http://localhost:8000/api/evaluation/compare \
  -H "Content-Type: application/json" \
  -d '{"game_ids": ["id1", "id2"]}'

# 整体统计
curl http://localhost:8000/api/evaluation/stats
```

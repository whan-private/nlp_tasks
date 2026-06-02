import asyncio
import argparse
from typing import Dict
from main_demo import run_demo, GameController

async def evolve_loop(iterations: int, config_name: str, log_level: str):
    """
    运行自进化循环：多次对局，并在每局后由 SummaryAgent 分析、生成经验。
    由于 player_agent 每次都会加载经验作为 prompt，这天然形成了一个自进化循环。
    """
    print("=" * 60)
    print(f"🐺 开始自进化训练循环 🐺")
    print(f"计划局数: {iterations}")
    print(f"对局配置: {config_name}")
    print("=" * 60)

    stats = {
        "good_wins": 0,
        "evil_wins": 0,
        "total_games": 0,
        "good_win_rate": 0.0,
    }

    for i in range(1, iterations + 1):
        print(f"\n[{i}/{iterations}] 正在进行第 {i} 局对战...")
        try:
            # 使用自动模式跑完一局
            record = await run_demo(
                config_name=config_name,
                player_styles=None, # 默认风格
                shuffle=True,       # 打乱角色
                save_record=True,
                log_level=log_level,
                control_mode=GameController.MODE_AUTO,
            )
            
            winner = record.winner
            stats["total_games"] += 1
            if winner == "good":
                stats["good_wins"] += 1
                print(f"🏆 第 {i} 局结束，胜者：善良阵营(好人)")
            elif winner == "evil":
                stats["evil_wins"] += 1
                print(f"🏆 第 {i} 局结束，胜者：邪恶阵营(狼人)")
            else:
                print(f"🏆 第 {i} 局结束，胜者：{winner}")
                
            # 计算当前胜率
            stats["good_win_rate"] = stats["good_wins"] / stats["total_games"]
            print(f"📈 当前战绩：好人 {stats['good_wins']} 胜，狼人 {stats['evil_wins']} 胜 (好人胜率: {stats['good_win_rate']:.1%})")
            
        except Exception as e:
            print(f"❌ 第 {i} 局发生错误: {e}")

    print("\n" + "=" * 60)
    print("🎉 自进化训练循环结束 🎉")
    print(f"总局数: {stats['total_games']}")
    print(f"好人胜场: {stats['good_wins']}")
    print(f"狼人胜场: {stats['evil_wins']}")
    print(f"最终好人胜率: {stats['good_win_rate']:.1%}")
    print("各角色的经验（Prompt）已在对局后自动更新并保存至 memory/experiences/ 目录下。")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="自进化训练循环")
    parser.add_argument("--iters", "-n", type=int, default=5, help="训练局数")
    parser.add_argument("--config", "-c", default="standard_6", choices=["standard_6", "simple_4", "big_9"], help="角色配置")
    parser.add_argument("--log-level", "-l", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别 (建议使用WARNING以减少输出)")
    
    args = parser.parse_args()
    asyncio.run(evolve_loop(args.iters, args.config, args.log_level))

if __name__ == "__main__":
    main()

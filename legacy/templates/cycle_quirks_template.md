# 短期风格覆写 (Cycle Quirks)
# 叙事空间创作系统 v8.5
#
# 作用范围：当前卷（volume_scope 声明的卷）
# 优先级：最高（注入 write_constraints 尾部，Prompt 末位强注意力区）
# 生命周期：每卷结束时由 volume_snapshot.py 自动归档并清空
#
# 使用方式：
#   1. 直接编辑本文件添加本卷临时偏好
#   2. 或运行 python scripts/update_style_rule.py --scope cycle --project-dir .
#   3. volume_snapshot.py 卷末会将本文件内容归档到对应 snapshot，并重置本文件

---
volume_scope: 1        # 本规则适用的卷号（由 init.py 填写）
last_updated: ""       # 最后更新时间
source: "manual | update_style_rule.py"
---

## 本卷临时规则

<!-- 在此添加仅在本卷生效的风格偏好 -->
<!-- 优先级：本层 > dna_human_*.yaml > clone_*.yaml > global_author_dna > 内置规则 -->

<!-- 示例规则（取消  <!-- 注释后激活）: -->
<!-- - 本卷打斗场景要求「动词精准、拳拳到肉」，禁止模糊表达如「砸向」「打在」 -->
<!-- - 本卷要求多描写路人目击者的震惊反应（三层震惊链：执行者→围观→权威）  -->

## 归档记录（上卷清理后自动填入）

<!-- 本区域由 volume_snapshot.py 写入，请勿手动编辑 -->

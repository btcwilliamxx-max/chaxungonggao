# chaxungonggao - 违规通知下发索引

查询群违规通知 (818 共识 · 违规通知) 的下发辅助页:点击群名直接跳 Telegram 群 + 一键复制通知文本。

**在线访问**: https://btcwilliamxx-max.github.io/chaxungonggao/

## 用法

1. 把新的违规通知 .txt 文件 (MMDD.txt, 跟 0827.txt 同格式) 复制到本目录
2. 跑脚本重新生成 index.html:
   ```bash
   cd G:/餐补/chaxungonggao
   python -X utf8 gen_violation_html.py
   ```
3. commit + push:
   ```bash
   git add . && git commit -m "add MMDD 违规通知" && git push
   ```
4. GitHub Pages 1-2 min 自动更新, 刷新 `https://btcwilliamxx-max.github.io/chaxungonggao/` 即可

## 页面功能

- 顶部搜索栏: 按群名 / 地址 / 触发项 / 发送至过滤
- 群名点击直接跳对应查询群 (TG 私域深链 `tg://resolve?domain=c/{chat_id}`)
- 通知文本默认折叠 1 行 preview, 点击展开全文
- 一键 "复制通知" 按钮, 跳过 ✂ 分隔线复制纯通知文本
- 🏠 跳转群按钮 (橙色, TG 深链直达)

## ⚠️ 跳转群前提

私域群 (没公开 username) 必须用 `tg://` 协议唤起 Telegram Desktop 客户端才能进群。
**要求**: Windows 必须装 [Telegram Desktop 客户端](https://desktop.telegram.org/)

- ✅ 浏览器点 `tg://resolve?domain=c/{chat_id}` → 弹"在 Telegram 中打开"对话框 → 确认 → 直接进群
- ❌ 用 `https://t.me/c/{chat_id}` 浏览器会被 TG 服务器重定向到 telegram.org 主页 (因为没装浏览器扩展 + 没在 web.telegram.org 登录)
- ❌ 群组映射表里没存 invite_link (8/27 拉 s2 dialogs 时漏了), 暂时没 invite 链接 fallback

如果 Windows 没装 Telegram Desktop, 点跳转群会提示"找不到应用", 装一下即可。

## 数据源

- `0827.txt` 原始数据备份 (用户提供的违规通知源文件)
- 群组映射: `G:\餐补\群组映射表.json` (8/27 1034 群, 561 查询群子集)
- 智能匹配: 去前缀 `N-` / 去后缀 `查询群/查詢群` / 模糊 substring 双向匹配

## 已知限制

- 群名 = `-` 的源数据 (0827.txt 第 29/54 条) 无法匹配, 会显示 ❌
- 群组映射表更新后需重新跑 `gen_violation_html.py` 才能让新群名匹配上

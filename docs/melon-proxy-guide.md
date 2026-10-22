# Melon Fleet 代理中心教程页

固定公开入口：`https://ticket-pro-website.vercel.app/help/melonfleet/proxy`。

正文来自 2026-10-22 读取的飞书《Melon fleet教程》中“代理中心”与“手动构建端口”两节，包括 FlClash 脚本、覆写步骤、任务代理地址，以及 macOS / Windows 出口 IP 检查命令。原文地址：<https://my.feishu.cn/wiki/ZW3awfYEFianj0kencmcBj59nec>。

页面位于 `src/pages/MelonProxyGuide.jsx`，样式位于 `src/pages/melon-proxy-guide.css`。通过 React Router 独立展示，复用 Vercel 的 SPA rewrite，按需加载，不在商品目录增加公开导航。访问不需要登录。

脚本模板位于 `src/data/tutorials/flclash-melon-multi-port.txt`，原样复制自“批量melon”项目的 `docs/flclash_melon_multi_port.js`。下载文件名为 `flclash_melon_multi_port.js`。页面只替换 `TASK_COUNT` 的整数值，允许 1 至 200 个任务，起始端口固定为 17891。更新脚本时同步此模板，不要修改引号、反引号或代码换行。

飞书文档可保留以下入口文字（本次没有修改飞书原文）：

> 代理中心与多端口配置教程已迁移到独立网页，包含 FlClash 配置、完整脚本和出口 IP 检查步骤。请打开：
> https://ticket-pro-website.vercel.app/help/melonfleet/proxy

本地验证：前端 lint 与生产构建；桌面、390px 手机视口；目录跳转、复制、下载、任务数量边界。脚本与原版逐字一致，验证 1 / 3 / 10 / 200 个任务的端口范围及重复应用。

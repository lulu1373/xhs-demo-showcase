# GitHub Pages 发布说明

这个目录已经是可直接部署到 GitHub Pages 的站点目录。

## 主页

- `index.html`

## 包含页面

- `xhs_workflow_milestone.html`
- `xhs_user_profile_visual_4429.html`
- `xhs_assessment_result_demo.html`
- `xhs_persona_report_cards.html`
- `xhs_project_demo_word_from_desktop.html`

## 最短发布步骤

1. 在 GitHub 新建一个仓库。
2. 把 `docs/` 目录里的全部文件上传到仓库里的 `docs/` 文件夹。
3. 打开 GitHub 仓库页面：
   - `Settings`
   - `Pages`
4. 在 `Build and deployment` 中设置：
   - `Source`: `Deploy from a branch`
   - `Branch`: `main`
   - `Folder`: `/docs`
5. 保存后等待几十秒到几分钟。
6. GitHub 会生成一个链接，格式通常是：
   - `https://你的用户名.github.io/仓库名/`

## 本地预览

直接双击 `index.html` 即可，或运行：

```bash
open /Users/lulu/AIWork/docs/index.html
```

# 教育动画与日常科普 Skill

可移植版 1.1.0，更新日期：2026-09-19。

将经过多轮迭代的视频制作规则与执行流程打包，让另一个 Agent 不依赖原始对话也能继续制作。日常科普与无声几何动画是独立模式。

## 导入

支持 Skills CLI 的环境可执行：

```bash
npx skills add tom729/educational-video-recreation
```

也可以下载或克隆本仓库，把整个 `educational-video-recreation/` 目录放到目标 Agent 指定的技能目录。其他工具不需要识别 `agents/openai.yaml`。

```bash
git clone https://github.com/tom729/educational-video-recreation.git
```

当前 Codex 本机安装位置通常为用户技能目录；具体路径由该环境配置决定。已有同名技能时先比对并保留本地修改，不盲目覆盖。

没有技能导入功能时，直接把目录作为项目附件，并发送：

> 请读取 educational-video-recreation/SKILL.md，以及其中当前任务需要的 references 文件，按该流程完成我的科普视频任务。不要依赖任何历史对话。

## 内容

- [SKILL.md](SKILL.md)：能力入口、模式和交付要求。
- [日常制作规范](references/daily-science-production.md)：画幅留白、封面、分段、真实结构、配音尾音、发音、转场、结尾与默认暂停。
- [完整制作流程](references/production-workflow.md)：资料、脚本、分镜、配音、时间轴、动画、导出、验收、修订和项目接续。
- [Blender 3D 制作](references/blender-production.md)：程序化建模、真实结构、材质灯光、拆解与吊装、镜头衔接、透明渲染和工程交付。
- [Blender 起步脚本](scripts/create_blender_scene.py)：创建可编辑示例场景，逐帧检查几何留白，可抽帧试渲染；不是完整科普视频。
- [跨 Agent 适配与调用](references/portability.md)：导入方法、能力替代和使用示例。
- [几何案例](references/geometry-case.md)：独立几何模式参考，日常科普无需读取。
- [视频核验脚本](scripts/verify_video.py)：格式、时长、音轨存在性、首帧提取和疑似长静帧检测。

## 默认预设

日常科普：1080×1920、30 fps、中文配音与短句字幕；顶部20%、底部10%、左右各10%留白；第0帧即封面；无品牌；局部放大与整体衔接；默认暂停、不自动连播。时长以讲清楚为准，用户新要求优先。

## 使用范围

这是可复制的制作技能包，不包含成片、个人资料、账号令牌或语音/图像模型。使用者需要自己的渲染与配音能力；缺少能力时 Agent 应如实交付已完成部分。数值检查不等于已试听或已验证全部画面。

本包不会自动上传素材、安装依赖、发布视频或调用付费服务。它提供可迁移的制作流程，具体操作仍由使用者授权。

## 调用示例

> 使用 educational-video-recreation，制作“汽车是金属的，为什么还能躲雷？”科普视频。先核对科学依据并输出脚本和分镜，我确认后再制作。

# Krea2 高质量底板 · 测试卡

## 定位
仅用于验证 Krea2 生图画质，**不接入现役 N4 出图链**。
原版 `▶▷Krea2-单采极清生图流+SeedVR2-int8图像放大.json` 未做任何改动。

## 文件
- 源：`D:\AIShortDrama\2_工作流\03-其他\测试-Krea2高质量底板-1344x768.json`
- GUI 副本：`D:\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\03-其他-Krea2测试\`

## 相对原卡的改动（5 处）
1. **尺寸**：断开 `ResolutionSelector(#17)` → `EmptyLatentImage(#16)` 的 width/height 连线，直连写死 `1344×768`（横屏）。
2. **prompt**：`CLIPTextEncode(#165)` 改为通用角色板底板描述，去掉"鎏金烈焰舞姬"身份，保留全身/脚/鞋子/地面约束。
3. **输出**：新增 `SaveImage(#196)` 直连 `VAEDecode(#14)`，前缀 `Krea2测试-底板`，不覆盖现役 `底板-脚全.png`。
4. **放大链**：SeedVR2 + USD + Sharpen + 批量压缩保持旁通（25 个旁通节点不变）。
5. **说明**：新增 `Note(#197)` 标注测试卡用途。

## 测试步骤
1. GUI 打开 `03-其他-Krea2测试/测试-Krea2高质量底板-1344x768.json`
2. 确认下方模型已就位
3. Queue Prompt，等待生成
4. 检查输出图 `Krea2测试-底板_*.png`

## 验收关注点
- 全身是否入镜，脚部 / 鞋子 / 地面是否完整
- 皮肤、织物、光影细节是否明显优于 Z-Image 底板
- 是否有文字 / 水印污染

## 需人工下载的模型
- `Krea2\Krea2-moodyKrea2Mix_v8_int8_convrot.safetensors`
- `qwen3vl_4b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`（本机已有）

## 验证通过后如何接入现役链（本次不执行）
把输出前缀改成 `底板-脚全`，卡移到 `2_工作流\02-漫剧\01-分镜图片\`，按权威规则同步底座与 GUI；
A2 `LoadImage(#10)` 会自动读到新底板。此步需单独确认后再做。


---

# Krea2 图生图（i2i）· 测试卡

## 定位
基于文生图测试卡派生，用于验证 **Krea2 对已有底板的重绘提质**（拿现成角色板/三视图去提质感），
不接入现役链。文生图测试卡与原版卡均未改动。

## 文件
`测试-Krea2图生图-1344x768.json`（源 + GUI 副本，与文生图卡同目录）

## 相对文生图卡的改动
1. 新增生效 `LoadImage(#198)` → `VAEEncode(#199)` → `KSampler(#186).latent_image`（替换原 `EmptyLatentImage` 的 link 234）
2. `VAEEncode` 复用 `#24 qwen_image_vae`，与原卡解码器同源
3. `denoise = 0.4`（保留原构图，调高更自由但易跑偏/丢脸）
4. `EmptyLatentImage(#16)` 设旁通备用；输出前缀改 `Krea2测试-图生图`
5. Note 同步更新

## 测试步骤
1. GUI 打开 `03-其他-Krea2测试/测试-Krea2图生图-1344x768.json`
2. 在 `LoadImage(#198)` 选择输入图（建议先缩放到 1344×768，避免构图被强制拉伸）
3. Queue Prompt，检查 `Krea2测试-图生图_*.png`
4. 对照原图：细节是否提升、构图和脸是否保留、denoise 是否合适（可试 0.3 / 0.4 / 0.5）

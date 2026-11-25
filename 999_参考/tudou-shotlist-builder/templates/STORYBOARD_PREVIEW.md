# 可视化分镜组件

本组件是 HTML_TEMPLATE.md 唯一新增的局部样式/交互扩展，不改原视频提示词块、过滤器、统计或配色。每个场景按页插入。占位符全部来自同一镜头格表，交付时不能残留。

## 放置与生成状态

画幅文字必须区分“目标单格比例”和“实际测量结论”。未通过实际内框比例验收时显示“目标16:9；当前画幅不合格／待核验”，不得仅凭清单声明显示“已验收·单格16:9”。保存实际绘图调用提示词；后补的修订提示词明确标为待重绘版本。不得通过CSS拉伸、裁切或加空白修饰不合格原图。音频意向未答或绑定未定时，相关视频提示词显示“草稿，音频参考待确认”，不影响独立预览展示。

`{SCENE_STORYBOARD_PREVIEWS}` 放在场景头之后、文字分镜表之前。默认展开图片；文字格表与绘图提示词可折叠。仅当图片真实存在且版本一致时渲染图片/放大组件；pending 时只显示“待生成”、格表和绘图提示词，不插 broken image 或空白图假装成品。failed / stale 明确标注“待修／已过期，不能作为已批准分镜”。

下列片段适用于有真实图像的页面。`{SB_UID}` 在整个HTML唯一；不得使用 `.prompt-block`、`.h3-unit` 或 `data-duration-seconds` 来包装预览。

```html
<section class="sb-preview" id="{SB_UID}" data-sb-page="{PAGE_ID}" data-sb-scene="{SCENE_ID}" data-sb-revision="{REVISION}" data-sb-status="{STATUS_MACHINE}" aria-labelledby="{SB_UID}-title">
  <h3 id="{SB_UID}-title">可视化分镜 · {SCENE_LABEL} · 第{PAGE_NUMBER}页</h3>
  <p>版本 {REVISION} · {STATUS_ZH} · 单格 {ASPECT_RATIO} · 素描仅用于镜头预演</p>
  <figure>
    <img class="sb-sheet" src="{IMAGE_DATA_URI}" alt="{NINE_PANEL_ALT}" loading="lazy">
    <figcaption>{COVERAGE_SUMMARY}；格号不是新增镜头，连续关键帧不重复计时。</figcaption>
  </figure>
  <button type="button" data-sb-open="{SB_UID}-zoom">放大查看九宫格</button>
  <dialog class="sb-zoom" id="{SB_UID}-zoom" aria-label="九宫格分镜放大图">
    <form method="dialog"><button type="submit" autofocus>关闭放大图</button></form>
    <img src="{IMAGE_DATA_URI}" alt="{NINE_PANEL_ALT}">
  </dialog>
  <details>
    <summary>查看格号与镜头对应关系</summary>
    <div class="sb-table-wrap"><table>
      <thead><tr><th>格号</th><th>镜号／时间</th><th>画面与表演</th><th>动线／连续性</th></tr></thead>
      <tbody>{PANEL_ROWS}</tbody>
    </table></div>
  </details>
  <details>
    <summary>中文版素描绘图提示词（不是视频提示词）</summary>
    <button type="button" data-sb-copy="{SB_UID}-draw">复制绘图提示词</button>
    <pre class="sb-drawing-prompt" id="{SB_UID}-draw" data-sb-drawing-prompt="true">{DRAWING_PROMPT_ZH}</pre>
    <span class="sb-copy-status" role="status" aria-live="polite"></span>
  </details>
</section>
```

`{PANEL_ROWS}` 每格一行，且必须使用 `<tr data-sb-cell="{CELL}" data-sb-shot="{SHOT_ID}" data-sb-at="{ABSOLUTE_TIME}">`。未用格使用 `<tr data-sb-cell="{CELL}" data-sb-unused="true">`；镜号用锚点指向真实镜头行（为该行赋稳定唯一ID）。同镜 a/b/c 标为“连续，无剪切”；未用格写“未使用”，不建立虚假链接。原文对白只在原镜头表保留，不复制到图片文字中。

## 待生成也必须可见的九宫格

`pending`、`failed` 或 `stale` 页面没有真实图片时，不能退化成文字卡片、单位列表或只在 JSON 里保存格表。使用下面的可见占位九宫格；它是审稿用的格位与因果地图，不冒充已经绘制的素描。每页必须恰好九个 `.sb-pending-cell`，并与 manifest 的同页 `panels` 一一对应。

```html
<section class="sb-preview" id="{SB_UID}" data-sb-page="{PAGE_ID}" data-sb-scene="{SCENE_ID}" data-sb-revision="{REVISION}" data-sb-status="pending" aria-labelledby="{SB_UID}-title">
  <h3 id="{SB_UID}-title">可视化分镜 · {SCENE_LABEL} · 第{PAGE_NUMBER}页</h3>
  <p>版本 {REVISION} · 待生成 · 目标单格 {ASPECT_RATIO}；当前显示可审阅的九宫格格位，不冒充实际素描。</p>
  <div class="sb-pending-grid" aria-label="{SCENE_LABEL} 第{PAGE_NUMBER}页九宫格">
    <article class="sb-pending-cell" data-sb-cell="1" data-sb-shot="{SHOT_ID_1}" data-sb-at="{ABSOLUTE_TIME_1}"><b>{FRAME_LABEL_1}</b><span>{SHOT_TIME_1}</span><p>{VISUAL_1}</p><small>{CONTINUITY_1}</small></article>
    {PENDING_CELLS_2_TO_9}
  </div>
  <details open>
    <summary>查看格号与镜头对应关系</summary>
    <div class="sb-table-wrap"><table><thead><tr><th>格号</th><th>镜号／时间</th><th>画面与表演</th><th>动线／连续性</th></tr></thead><tbody>{PANEL_ROWS}</tbody></table></div>
  </details>
  <details>
    <summary>中文版素描绘图提示词（不是视频提示词）</summary>
    <button type="button" data-sb-copy="{SB_UID}-draw">复制绘图提示词</button>
    <pre class="sb-drawing-prompt" id="{SB_UID}-draw" data-sb-drawing-prompt="true">{DRAWING_PROMPT_ZH}</pre>
    <span class="sb-copy-status" role="status" aria-live="polite"></span>
  </details>
</section>
```

未用格的唯一合法形态为：

```html
<article class="sb-pending-cell unused" data-sb-cell="{CELL}" data-sb-unused="true"><b>未使用</b><span>不新增镜头</span></article>
```

不要为补足九格发明人物、道具、台词或动作。生成/验收实际图片后，再把同一 `data-sb-page` 页面替换为上方的图片组件；格号、shot、at、绘图提示词与 manifest 不能悄悄变化。

## 一次性局部 CSS

```css
.sb-preview{margin:20px 0;padding:18px;border:1px solid #555;border-radius:10px}
.sb-preview figure{margin:12px 0}.sb-sheet{display:block;width:100%;height:auto;background:#fff}
.sb-preview button,.sb-preview summary{cursor:pointer}.sb-preview details{margin-top:12px}
.sb-table-wrap{overflow:auto}.sb-preview table{width:100%;border-collapse:collapse}
.sb-preview th,.sb-preview td{padding:8px;border-bottom:1px solid #666;text-align:left;vertical-align:top}
.sb-drawing-prompt{white-space:pre-wrap;overflow-wrap:anywhere;max-height:28rem;overflow:auto}
.sb-pending-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0}.sb-pending-cell{aspect-ratio:16/9;border:1px solid #66717c;background:#222b35;padding:8px;display:flex;flex-direction:column;overflow:auto}.sb-pending-cell b{color:#f3d293}.sb-pending-cell span,.sb-pending-cell small{color:#aeb8c3;font-size:11px}.sb-pending-cell p{margin:5px 0;font-size:12px;line-height:1.35}.sb-pending-cell.unused{background:#151b22;justify-content:center;text-align:center;color:#7d8792}
.sb-zoom{width:94vw;max-width:none;max-height:94vh;overflow:auto;background:#fff;color:#111}
.sb-zoom::backdrop{background:#000b}.sb-zoom img{display:block;width:100%;height:auto;min-width:1000px}
.sb-zoom form{position:sticky;top:0;margin-bottom:8px}
@media(max-width:760px){.sb-pending-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media print{.sb-preview button,.sb-zoom,.sb-preview details{display:none}.sb-preview{break-inside:avoid}}
```

## 一次性局部 JS

```javascript
document.querySelectorAll('[data-sb-open]').forEach(button => {
  button.addEventListener('click', () => {
    const dialog = document.getElementById(button.dataset.sbOpen);
    if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
  });
});
document.querySelectorAll('[data-sb-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    const source = document.getElementById(button.dataset.sbCopy);
    const status = button.parentElement.querySelector('.sb-copy-status');
    try {
      await navigator.clipboard.writeText(source.textContent);
      status.textContent = ' 已复制';
    } catch (_) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(source);
      selection.removeAllRanges(); selection.addRange(range);
      status.textContent = ' 已选中文本，请按 Ctrl+C 复制';
    }
  });
});
```

所有正文/属性值均HTML转义；绘图提示词以 textContent 复制。data URI 仅由本地已检查图片字节生成，不插远端脚本。图片 src 与放大图使用同一份数据。按本场过滤显隐，不把每一格交给视频镜头计数器。

交付检查：离线打开图片、打开/关闭弹窗、键盘Esc、复制成功或降级选中、镜号跳转、窄窗口横向滚动；加入组件前后 H3 单元数量与计算总时长必须不变。没有真实图片的维护测试用明确标注的测试图，不得把测试页交成剧情分镜图。

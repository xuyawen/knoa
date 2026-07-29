// 蒙层关闭手势修正：把"单击蒙层关闭"从原生的 @click.self 升级为
// 「按下与松开都落在蒙层自身、且鼠标几乎无位移」才算一次明确单击。
//
// 原生 @click.self 只判断 mousedown/mouseup 的 target 是否都是蒙层自身，
// 不判断鼠标有没有移动——所以从弹窗拖进蒙层（或蒙层拖进弹窗）再松手，
// 只要起止都落在蒙层上，浏览器仍当 click 触发关闭（拖拽误关）。
//
// 用法：在蒙层元素上同时绑定 onMouseDown / onMouseUp，
//   <div class="overlay" @mousedown="bd.onMouseDown" @mouseup="bd.onMouseUp">
//   const bd = useBackdropClick(() => emit('close'))
const DRAG_THRESHOLD = 8 // 像素：曼哈顿位移超过此值视为拖拽，不关闭

export function useBackdropClick(onDismiss: () => void) {
  let downX = 0
  let downY = 0
  let downOnSelf = false

  function onMouseDown(e: MouseEvent): void {
    // 只在蒙层自身（非内部卡片）按下时才记录，从弹窗里按下的不算
    downOnSelf = e.target === e.currentTarget
    downX = e.clientX
    downY = e.clientY
  }

  function onMouseUp(e: MouseEvent): void {
    if (!downOnSelf) return // 起点不在蒙层
    if (e.target !== e.currentTarget) return // 终点不在蒙层（拖进弹窗了）
    const moved = Math.abs(e.clientX - downX) + Math.abs(e.clientY - downY)
    if (moved > DRAG_THRESHOLD) return // 有明显拖拽位移，不是明确单击
    onDismiss()
  }

  return { onMouseDown, onMouseUp }
}

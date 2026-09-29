from __future__ import annotations

from typing import Any


_ZH_CN: dict[str, str] = {
    "app.name": "Rita Desktop Pet",
    "menu.refresh": "刷新额度",
    "menu.show_usage": "显示额度信息",
    "menu.always_on_top": "始终置顶",
    "menu.lock_position": "锁定位置",
    "menu.skin": "皮肤",
    "menu.interactions": "互动设置",
    "menu.auto_skin": "自动换肤",
    "menu.opacity": "透明度",
    "menu.refresh_interval": "刷新间隔",
    "menu.startup": "开机启动",
    "menu.create_shortcut": "创建桌面快捷方式",
    "menu.delete_shortcut": "删除桌面快捷方式",
    "menu.open_logs": "打开日志目录",
    "menu.about": "关于",
    "menu.exit": "退出",
    "dialog.interactions.title": "互动动作",
    "dialog.interactions.subtitle": "选择点击互动与随机待机时可能播放的动作",
    "dialog.quiet.title": "安静模式",
    "dialog.quiet.description": "减少日常互动动作，让桌宠保持安静",
    "dialog.restore": "恢复当前皮肤默认设置",
    "dialog.cancel": "取消",
    "dialog.save": "保存",
    "dialog.restore.confirm": "恢复“{skin}”的默认互动设置？",
    "source.default": "当前：皮肤默认",
    "source.custom": "当前：自定义",
    "event.hover": "鼠标悬停",
    "event.hover.description": "鼠标移动到人物上时",
    "event.click": "点击人物",
    "event.click.description": "点击丽塔时",
    "event.idle_random": "随机待机",
    "event.idle_random.description": "日常待机时偶尔出现",
    "event.low": "额度较低",
    "event.low.description": "剩余额度为 10%～30% 时",
    "event.critical": "额度紧张",
    "event.critical.description": "剩余额度低于 10% 时",
    "event.empty": "额度耗尽",
    "event.empty.description": "剩余额度为 0% 时",
    "event.recovered": "额度恢复",
    "event.recovered.description": "额度重置并恢复后",
    "event.enter": "进入状态",
    "event.idle": "持续姿态",
    "event.exit": "离开状态",
    "action.none": "不做动作",
    "action.idle": "安静站立",
    "action.blink": "眨眼",
    "action.smile": "微笑",
    "action.hover": "轻轻侧头",
    "action.click": "点击回应",
    "action.click_react": "点击回应",
    "action.wave": "挥手",
    "action.stretch": "整理头发",
    "action.soft_stretch": "轻微舒展",
    "action.tidy_hair": "整理头发",
    "action.tidy_skirt": "整理裙摆",
    "action.small_bow": "轻轻鞠躬",
    "action.gentle_sigh": "轻轻叹气",
    "action.sit_transition": "缓缓坐下",
    "action.sit": "坐下",
    "action.sit_idle": "坐着休息",
    "action.look_left": "看向左侧",
    "action.look_right": "看向右侧",
    "action.walk": "散步",
    "action.critical": "疲惫",
    "action.sleep": "睡觉",
    "action.sleep_react": "被吵醒",
    "action.sleepy": "犯困",
    "action.surprised": "轻微惊讶",
    "action.recovered": "恢复精神",
    "state.normal": "状态正常",
    "state.low": "额度较低",
    "state.critical": "额度紧张",
    "state.empty": "额度耗尽",
    "state.recovered": "额度恢复",
    "usage.five_hour": "5 小时",
    "usage.weekly": "每周",
    "usage.remaining": "剩余 {value}%",
    "usage.reading": "正在读取额度…",
    "usage.reset_unknown": "恢复时间未知",
    "usage.credits": "额度点数   {value}",
    "usage.reset_pass": "重置次数   {value}",
}


def tr(key: str, default: str | None = None, **values: Any) -> str:
    """Return localized text with a safe, visible fallback for missing keys."""
    text = _ZH_CN.get(key, default if default is not None else key)
    try:
        return text.format(**values)
    except (KeyError, ValueError):
        return text


def action_name(action_id: str) -> str:
    return tr(f"action.{action_id}", action_id.replace("_", " "))


def state_name(state_id: str) -> str:
    return tr(f"state.{state_id}", state_id.replace("_", " "))


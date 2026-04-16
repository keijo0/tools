#!/usr/bin/env python3
from evdev import InputDevice, categorize, ecodes, UInput, list_devices
from select import select
import time
import os
import threading

TAP_INTERVAL = 0.10   # Time between taps (seconds) — lower = faster walk
TAP_DURATION = 0.07   # How long each tap is held
COUNTER_STRAFE_DURATION = 0.05  # How long to hold the opposite key to kill velocity

MOVE_KEYS = {
    ecodes.KEY_W,
    ecodes.KEY_A,
    ecodes.KEY_S,
    ecodes.KEY_D,
}

# Opposite key for counter-strafing
OPPOSITE_KEY = {
    ecodes.KEY_W: ecodes.KEY_S,
    ecodes.KEY_S: ecodes.KEY_W,
    ecodes.KEY_A: ecodes.KEY_D,
    ecodes.KEY_D: ecodes.KEY_A,
}

def find_devices():
    keyboard_candidates = []
    mouse_candidates = []

    print("Scanning devices...")
    print("-" * 50)

    for path in list_devices():
        try:
            device = InputDevice(path)
            caps = device.capabilities()
            name_lower = device.name.lower()

            device_type = None
            by_id_link = None
            by_id_path = "/dev/input/by-id/"
            if os.path.exists(by_id_path):
                for link in os.listdir(by_id_path):
                    link_path = os.path.join(by_id_path, link)
                    if os.path.islink(link_path):
                        target = os.path.realpath(link_path)
                        if target == path:
                            if "-kbd" in link:
                                device_type = "kbd"
                                by_id_link = link
                            elif "-mouse" in link:
                                device_type = "mouse"
                                by_id_link = link
                            break

            type_info = f"type: {device_type}" if device_type else "type: None"
            if by_id_link:
                type_info += f" ({by_id_link})"
            print(f"{path}: {device.name} [{type_info}]")

            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                has_rel_movement = (ecodes.EV_REL in caps and
                                    ecodes.REL_X in caps[ecodes.EV_REL] and
                                    ecodes.REL_Y in caps[ecodes.EV_REL])

                if (ecodes.BTN_LEFT in keys and ecodes.BTN_RIGHT in keys and
                        has_rel_movement):
                    if device_type == "mouse" and "mouse" in name_lower:
                        priority = 0
                    elif "mouse" in name_lower:
                        priority = 1
                    elif device_type == "mouse":
                        priority = 2
                    else:
                        priority = 3
                    mouse_candidates.append((priority, device, path, by_id_link))
                    print(f"  -> MOUSE candidate (priority {priority})")

                elif (ecodes.KEY_SPACE in keys and ecodes.KEY_A in keys and
                      not has_rel_movement and "mouse" not in name_lower):
                    if device_type == "kbd":
                        if by_id_link and "-if" in by_id_link and "event-kbd" in by_id_link:
                            priority = 10
                        else:
                            priority = 0
                    else:
                        priority = 1000
                    keyboard_candidates.append((priority, device, path, by_id_link))
                    print(f"  -> KEYBOARD candidate (priority {priority})")
        except Exception:
            continue

    print("-" * 50)

    mouse_candidates.sort(key=lambda x: x[0])
    keyboard_candidates.sort(key=lambda x: x[0])

    mouse = mouse_candidates[0][1] if mouse_candidates else None
    keyboard = keyboard_candidates[0][1] if keyboard_candidates else None

    if mouse:
        mouse_link = f" ({mouse_candidates[0][3]})" if mouse_candidates[0][3] else ""
        print(f"Selected MOUSE: {mouse_candidates[0][2]} ({mouse.name}){mouse_link}")
    if keyboard:
        kbd_link = f" ({keyboard_candidates[0][3]})" if keyboard_candidates[0][3] else ""
        print(f"Selected KEYBOARD: {keyboard_candidates[0][2]} ({keyboard.name}){kbd_link}")

    if not keyboard or not mouse:
        missing = []
        if not keyboard:
            missing.append("keyboard")
        if not mouse:
            missing.append("mouse")
        raise RuntimeError(f"Could not auto-detect {' and '.join(missing)}")

    return keyboard, mouse


kb, mouse = find_devices()
devices = {kb.fd: kb, mouse.fd: mouse}
ui = UInput()

script_enabled = False
space_down = False

def shift_down():
    """Read shift state directly from hardware — never stale."""
    active = kb.active_keys()
    return ecodes.KEY_LEFTSHIFT in active or ecodes.KEY_RIGHTSHIFT in active

# Per-key slowwalk state: key_code -> {'active', 'thread', 'stop'}
slowwalk_states = {}

# Which move keys are physically held right now
held_move_keys = set()


def slowwalk_loop(key_code, stop_event):
    """Repeatedly tap a direction key until stopped."""
    # Counter-strafe once to kill velocity before tapping starts
    opposite = OPPOSITE_KEY.get(key_code)
    if opposite and not stop_event.is_set():
        ui.write(ecodes.EV_KEY, opposite, 1)
        ui.syn()
        time.sleep(COUNTER_STRAFE_DURATION)
        ui.write(ecodes.EV_KEY, opposite, 0)
        ui.syn()

    while not stop_event.is_set():
        ui.write(ecodes.EV_KEY, key_code, 1)
        ui.syn()
        time.sleep(TAP_DURATION)
        ui.write(ecodes.EV_KEY, key_code, 0)
        ui.syn()
        stop_event.wait(timeout=TAP_INTERVAL - TAP_DURATION)


def start_slowwalk(key_code):
    if key_code in slowwalk_states and slowwalk_states[key_code]['active']:
        return
    stop_event = threading.Event()
    thread = threading.Thread(
        target=slowwalk_loop,
        args=(key_code, stop_event),
        daemon=True
    )
    slowwalk_states[key_code] = {'active': True, 'thread': thread, 'stop': stop_event}
    thread.start()
    print(f"[SLOWWALK] Started -> {ecodes.KEY[key_code]}")


def stop_slowwalk(key_code):
    state = slowwalk_states.get(key_code)
    if not state or not state['active']:
        return
    state['active'] = False
    state['stop'].set()
    state['thread'].join(timeout=0.5)
    ui.write(ecodes.EV_KEY, key_code, 0)
    ui.syn()
    print(f"[SLOWWALK] Stopped -> {ecodes.KEY[key_code]}")
    del slowwalk_states[key_code]


def stop_all_slowwalk():
    for key_code in list(slowwalk_states.keys()):
        stop_slowwalk(key_code)


def is_slowwalking(key_code):
    return key_code in slowwalk_states and slowwalk_states[key_code]['active']


print("\nScript is Disabled (toggle with Mouse3/BTN_MIDDLE)")
print("Slowwalk: hold Shift + W/A/S/D to tap-walk in that direction")
print(f"  TAP_INTERVAL={TAP_INTERVAL}s  TAP_DURATION={TAP_DURATION}s")
print("-" * 50)

while True:
    r, _, _ = select(devices.keys(), [], [])
    for fd in r:
        dev = devices[fd]
        for event in dev.read():
            if event.type == ecodes.EV_KEY:
                key = event.code
                value = event.value  # 0=up, 1=down, 2=repeat

                # --- Toggle script with Middle Mouse ---
                if key == ecodes.BTN_MIDDLE and value == 1:
                    script_enabled = not script_enabled
                    state_str = "ENABLED" if script_enabled else "DISABLED"
                    print(f"[TOGGLE] Script is now {state_str}")
                    if not script_enabled:
                        stop_all_slowwalk()
                    continue

                # --- If script disabled, forward all events as-is ---
                if not script_enabled:
                    ui.write(event.type, event.code, value)
                    ui.syn()
                    continue

                # --- Track Shift side effects (state read from hardware) ---
                if key in (ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT):
                    if value == 1:
                        # Start slowwalk for any move keys already held
                        for mk in held_move_keys:
                            start_slowwalk(mk)
                    elif value == 0:
                        # Stop all slowwalks; restore held move keys as normal hold
                        stop_all_slowwalk()
                        for mk in held_move_keys:
                            ui.write(ecodes.EV_KEY, mk, 1)
                            ui.syn()
                    # Always forward Shift itself
                    ui.write(event.type, event.code, value)
                    ui.syn()
                    continue

                # --- Movement key handling (W/A/S/D) ---
                if key in MOVE_KEYS:
                    if value == 1:  # Key down
                        held_move_keys.add(key)
                        if shift_down():
                            start_slowwalk(key)
                            # Taps are handled by thread; don't forward raw keydown
                        else:
                            ui.write(event.type, event.code, value)
                            ui.syn()
                    elif value == 0:  # Key up
                        held_move_keys.discard(key)
                        if is_slowwalking(key):
                            stop_slowwalk(key)
                            # Thread already sent key-up; skip forwarding
                        else:
                            ui.write(event.type, event.code, value)
                            ui.syn()
                    elif value == 2:  # Repeat — suppress if slowwalking
                        if not is_slowwalking(key):
                            ui.write(event.type, event.code, value)
                            ui.syn()
                    continue

                # --- SPACE handling ---
                if key == ecodes.KEY_SPACE:
                    if value == 1 and not space_down:
                        ui.write(ecodes.EV_KEY, ecodes.KEY_SPACE, 1)
                        ui.syn()
                        time.sleep(0.02)
                        ui.write(ecodes.EV_KEY, ecodes.KEY_SPACE, 0)
                        ui.syn()
                        space_down = True
                    elif value == 0:
                        space_down = False
                    continue

                # --- Forward all other keys ---
                ui.write(event.type, event.code, value)
                ui.syn()
            else:
                # Forward non-key events (mouse movement, scroll, etc.)
                ui.write(event.type, event.code, event.value)
                ui.syn()

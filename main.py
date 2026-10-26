import os
import random

import pygame

# --- Config ---
WIDTH, HEIGHT = 960, 540
FPS = 60

BGC_COLOR = (24, 24, 32)   # dark wat night
LINE_COLOR = (200, 200, 210)
NARRATOR_COLOR = (150, 150, 165)
BAD_COLOR = (220, 90, 90)
TEXT_COLOR = (230, 230, 230)

MAX_ROUNDS = 999999999   # endless, Exit-8 style
MAX_MISTAKES = 3

CORRECT_COOLDOWN = 0.5  # seconds between answers (anti-mash)
FADE_TIME = 0.3       # seconds for the fade-to-black transition

TYPE_SPEED = 45       # characters per second for the typewriter effect

# --- Content ---
# anomaly list: (id, narration line, is_anomaly)
# The line is what the player reads; the is_anomaly flag stays hidden.
ANOMALIES = [
    ("no_shadow", "The 4th boy has no shadow on the wet road.", True),
    ("wrong_robe", "The 2nd boy wears a yellow robe tonight.", True),
    ("backwards", "The 6th boy walks with his back to the coffin.", True),
    ("tail_curl", "The naga's tail curls upward into the rain.", True),
    ("extra_lamp", "An extra lamp flickers beside the coffin.", True),
    ("normal_line", "The procession moves along as always.", False),
    ("normal_rain", "Rain beats softly on the temple roofs.", False),
    ("normal_monk", "A young monk whispers a prayer to himself.", False),
]

INTRO_LINES = [
    "You are a temple boy keeping watch over the naga procession.",
    "Watch carefully. Some nights the procession is not right.",
    "Press N if nothing is wrong, or A if something feels off.",
]

THAI_END_TEXT = "คุณกลายเป็นผีแล้ว"


# --- Audio ---
def start_rain_ambient():
    """Try to play a rain loop. Fails silently if no asset/audio device."""
    try:
        pygame.mixer.init()
    except pygame.error:
        return None

    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "rain.wav"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "rain.ogg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "rain.mp3"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(0.4)
                pygame.mixer.music.play(-1)
                return path
            except pygame.error:
                return None
    return None


# --- State ---
def reset_game():
    """Fresh game state. Starts in the intro sequence."""
    return {
        "round": 1,
        "max_rounds": MAX_ROUNDS,
        "paranoia": 0,
        "mistakes": 0,
        "phase": "intro",        # intro | watching | ghost_end
        "intro_index": 0,
        "current": None,
        "current_anomaly": None,
        "locked": False,
        "lock_timer": 0.0,
        "fade": 0.0,              # 0..1 black overlay alpha factor
        "fade_phase": None,       # None | "out" | "in"
        "typed_chars": 0,        # how many characters of the line are visible
        "type_timer": 0.0,
    }


def pick_anomaly():
    """Pick a random entry from the anomaly list."""
    aid, line, is_anomaly = random.choice(ANOMALIES)
    return {"id": aid, "name": aid, "desc": line, "line": line, "is_anomaly": is_anomaly}


def start_round(state):
    """Create the next event and reset the typewriter."""
    anomaly = pick_anomaly()
    state["current"] = anomaly
    state["current_anomaly"] = anomaly
    state["phase"] = "watching"
    state["typed_chars"] = 0
    state["type_timer"] = 0.0


def begin_fade(state):
    """Start the fade-to-black transition and lock input."""
    state["locked"] = True
    state["lock_timer"] = 0.0
    state["fade_phase"] = "out"
    state["fade"] = 0.0


def judge(state, said_anomaly):
    """Compare the player's call with truth. No feedback is shown."""
    if state["current"] is None or state["locked"]:
        return
    correct = said_anomaly == state["current"]["is_anomaly"]
    if not correct:
        state["mistakes"] += 1
        state["paranoia"] += 1
        if state["mistakes"] >= MAX_MISTAKES:
            state["phase"] = "ghost_end"
            return
    begin_fade(state)


def advance_round(state):
    """Move to the next round after the fade finishes."""
    state["round"] += 1
    if state["round"] > state["max_rounds"]:
        state["round"] = 1
    start_round(state)


def update(state, dt):
    """Advance timers each frame."""
    # Typewriter for the current line
    if state["phase"] in ("watching", "intro"):
        state["type_timer"] += dt
        target = typed_target(state)
        shown = int(state["type_timer"] * TYPE_SPEED)
        state["typed_chars"] = min(shown, len(target))

    # Fade transition: fade out to black, swap the line, then fade back in
    if state["fade_phase"] == "out":
        state["fade"] += dt / FADE_TIME
        if state["fade"] >= 1.0:
            state["fade"] = 1.0
            advance_round(state)
            state["lock_timer"] = 0.0
            state["fade_phase"] = "in"
    elif state["fade_phase"] == "in":
        state["fade"] -= dt / FADE_TIME

        if state["fade"] <= 0.0:
            state["fade"] = 0.0
            state["fade_phase"] = None

    # Cooldown unlock (only when not fading)
    if state["locked"] and state["fade_phase"] is None:
        state["lock_timer"] += dt
        if state["lock_timer"] >= CORRECT_COOLDOWN:
            state["locked"] = False


def typed_target(state):
    """Return the full text that should eventually be typed out."""
    if state["phase"] == "intro":
        return INTRO_LINES[ state["intro_index"] ]
    if state["current"] is None:
        return ""
    return state["current"]["line"]


def handle_key(state, key):
    """Route keyboard input based on phase."""
    if state["phase"] == "ghost_end":
        if key == pygame.K_r:
            state.update(reset_game())
        return

    if state["phase"] == "intro":
        # Advance through the three intro lines.
        if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_n, pygame.K_a):
            state["intro_index"] += 1
            state["typed_chars"] = 0
            state["type_timer"] = 0.0
            if state["intro_index"] >= len(INTRO_LINES):
                start_round(state)
        return

    if state["locked"]:
        return

    if key == pygame.K_n:
        judge(state, False)
    elif key == pygame.K_a:
        judge(state, True)


# --- Drawing ---
def draw_center_text(screen, font, text, color, y):
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(WIDTH // 2, y))
    screen.blit(surf, rect.topleft)


def draw_wrapped_text(screen, font, text, color, center_y, max_width):
    """Draw text centered, wrapping into multiple lines."""
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w) if cur else w
        if font.size(trial)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    line_height = font.get_linesize() + 6
    total = line_height * len(lines)
    start_y = center_y - total // 2
    for i, line in enumerate(lines):
        surf = font.render(line, True, color)
        rect = surf.get_rect(center=(WIDTH // 2, start_y + i * line_height + line_height // 2))
        screen.blit(surf, rect.topleft)


def draw_rain(screen, t):
    """Cheap rain streaks for mood."""
    import math
    for i in range(60):
        x = (i * 137 + t * 180) % WIDTH
        y = (i * 89 + t * 420) % HEIGHT
        pygame.draw.line(screen, (60, 60, 80), (x, y), (x - 2, y + 8), 1)


def draw_scene(screen, font, state, t):
    """Draw the current text line, typewriter-style."""
    draw_rain(screen, t)

    if state["phase"] == "intro":
        full = INTRO_LINES[state["intro_index"]]
        shown = full[:state["typed_chars"]]
        draw_wrapped_text(screen, font, shown, LINE_COLOR, HEIGHT // 2 - 40, WIDTH - 160)
        draw_center_text(screen, font, "Press Space", NARRATOR_COLOR, HEIGHT - 60)
        return

    if state["current"] is None:
        return
    full = state["current"]["line"]
    shown = full[:state["typed_chars"]]
    draw_wrapped_text(screen, font, shown, LINE_COLOR, HEIGHT // 2, WIDTH - 160)

    draw_center_text(screen, font, "N = Normal   A = Anomaly", NARRATOR_COLOR, HEIGHT - 60)


def draw_end(screen, font):
    """Draw the ghost ending."""
    draw_center_text(screen, font, THAI_END_TEXT, BAD_COLOR, HEIGHT // 2 - 20)
    draw_center_text(screen, font, "Press R to restart", TEXT_COLOR, HEIGHT // 2 + 30)


def draw_fade(screen, alpha):
    """Draw a black overlay with the given 0..255 alpha."""
    if alpha <= 0:
        return
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.fill((0, 0, 0))
    overlay.set_alpha(alpha)
    screen.blit(overlay, (0, 0))


# --- Main ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Monk Watch - Naga Procession")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 28)

    start_rain_ambient()

    state = reset_game()
    t = 0.0
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                handle_key(state, event.key)

        update(state, dt)

        screen.fill(BGC_COLOR)
        if state["phase"] == "ghost_end":
            draw_end(screen, font)
        else:
            draw_scene(screen, font, state, t)

        # Fade overlay after the scene so it covers everything.
        draw_fade(screen, int(state["fade"] * 255))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()

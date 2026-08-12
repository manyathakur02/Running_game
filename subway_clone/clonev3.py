"""
Subway Surfers-style endless runner -- fitness build.

Architecture note:
  Game logic never talks to pygame.key directly. It only asks an
  InputProvider for the current action state each frame. Today that's
  KeyboardInput. Later, PoseInput (webcam + MediaPipe) implements the
  exact same interface and gets swapped in with a one-line change in
  main() -- no changes to Game/Player/Obstacle code required.

Fitness note:
  Jump count, squat (duck) count, and an estimated calorie count are
  tracked and shown on the game-over screen. The calorie figure is a
  simple gamified estimate (fixed kcal per jump/squat + a small
  per-second baseline) -- it is NOT calibrated to your body weight or
  actual effort, so treat it as a fun in-game number, not a substitute
  for a real fitness tracker.
"""

import math
import random
import sys
from dataclasses import dataclass

import pygame

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 420, 700
LANE_COUNT = 3
LANE_WIDTH = WIDTH // LANE_COUNT
LANE_CENTERS = [LANE_WIDTH * i + LANE_WIDTH // 2 for i in range(LANE_COUNT)]

GROUND_Y = 560
PLAYER_W, PLAYER_H = 50, 76
DUCK_H = 42

GRAVITY = 1.6
JUMP_VELOCITY = -22
DUCK_FRAMES = 28          # how long a duck lasts, in frames

BASE_SCROLL_SPEED = 7.0
SPEED_CYCLE_SECONDS = 30.0   # full slow -> fast -> slow cycle length
MAX_SPEED_MULTIPLIER = 2.0   # peak speed = BASE_SCROLL_SPEED * this

OBSTACLE_MIN_GAP = 480
OBSTACLE_MAX_GAP = 700

SPAWN_LEAD_DISTANCE = 120  # px above the screen where obstacles spawn,
                            # before scrolling down into view

FPS = 60

# Rough, gamified calorie estimates -- see module docstring.
CAL_PER_JUMP = 0.25
CAL_PER_SQUAT = 0.32
CAL_PER_SECOND_ACTIVE = 0.045

WHITE = (222, 224, 228)     # soft off-white, not stark white -- less glare
DIM_WHITE = (168, 170, 180)
LANE_LINE = (58, 60, 72)

SHIRT_COLOR = (78, 150, 205)    # desaturated blue instead of neon
SHIRT_SHADOW = (52, 108, 155)
SHORTS_COLOR = (48, 58, 82)
SKIN_COLOR = (230, 188, 150)
HAIR_COLOR = (58, 44, 40)

CRATE_COLOR = (165, 90, 78)     # muted terracotta instead of saturated red
CRATE_LIGHT = (190, 112, 98)
HAZARD_ACCENT = (215, 175, 70)  # single soft accent, not a repeating stripe field
WHEEL_COLOR = (40, 40, 45)

BAR_COLOR = (205, 172, 80)      # muted gold instead of bright saturated yellow
BAR_LIGHT = (222, 195, 120)
POLE_COLOR = (110, 110, 122)

COIN_COLOR = (218, 178, 70)
COIN_SHADOW = (170, 132, 45)
COIN_SHINE = (238, 220, 175)


# ---------------------------------------------------------------------------
# Input layer -- this is the piece that stays stable while everything behind
# it changes later (keyboard today, pose detection next).
# ---------------------------------------------------------------------------
@dataclass
class ActionState:
    move_left: bool = False
    move_right: bool = False
    jump: bool = False
    duck: bool = False


class InputProvider:
    """Abstract interface. Any input source implements poll()."""

    def poll(self, events) -> ActionState:
        raise NotImplementedError


class KeyboardInput(InputProvider):
    """Discrete, edge-triggered keyboard control.

    Left/Right/Up/Space/Down fire once per keypress (not held-repeat),
    matching how a lane-change or jump should behave.
    """

    def poll(self, events) -> ActionState:
        state = ActionState()
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    state.move_left = True
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    state.move_right = True
                elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                    state.jump = True
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    state.duck = True
        return state


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
class Player:
    def __init__(self):
        self.lane = 1  # 0=left, 1=middle, 2=right
        self.x = LANE_CENTERS[self.lane]
        self.y = GROUND_Y
        self.vel_y = 0
        self.jumping = False
        self.duck_timer = 0

    @property
    def height(self):
        return DUCK_H if self.duck_timer > 0 else PLAYER_H

    @property
    def rect(self):
        h = self.height
        top = self.y - h
        return pygame.Rect(int(self.x - PLAYER_W // 2), int(top), PLAYER_W, h)

    def apply(self, action: ActionState):
        """Returns (jumped, ducked) -- True only on the frame an action
        actually takes effect, so the game can count real reps rather
        than raw key presses."""
        jumped = False
        ducked = False
        if action.move_left and self.lane > 0:
            self.lane -= 1
        if action.move_right and self.lane < LANE_COUNT - 1:
            self.lane += 1
        if action.jump and not self.jumping and self.duck_timer == 0:
            self.jumping = True
            self.vel_y = JUMP_VELOCITY
            jumped = True
        if action.duck and not self.jumping and self.duck_timer == 0:
            self.duck_timer = DUCK_FRAMES
            ducked = True
        return jumped, ducked

    def update(self):
        target_x = LANE_CENTERS[self.lane]
        self.x += (target_x - self.x) * 0.35

        if self.jumping:
            self.y += self.vel_y
            self.vel_y += GRAVITY
            if self.y >= GROUND_Y:
                self.y = GROUND_Y
                self.jumping = False
                self.vel_y = 0

        if self.duck_timer > 0:
            self.duck_timer -= 1

    def draw(self, surf):
        rect = self.rect
        cx = rect.centerx
        top, bottom = rect.top, rect.bottom
        w = rect.width
        ticks = pygame.time.get_ticks()

        if self.jumping:
            pose = "jump"
        elif self.duck_timer > 0:
            pose = "duck"
        else:
            pose = "run"

        # --- legs ---
        if pose == "run":
            offset = int(math.sin(ticks * 0.02) * 11)
            pygame.draw.line(surf, SHORTS_COLOR, (cx - 9, bottom - 4), (cx - 9 + offset, bottom + 14), 8)
            pygame.draw.line(surf, SHORTS_COLOR, (cx + 9, bottom - 4), (cx + 9 - offset, bottom + 14), 8)
        elif pose == "jump":
            pygame.draw.line(surf, SHORTS_COLOR, (cx - 9, bottom - 4), (cx - 15, bottom + 8), 8)
            pygame.draw.line(surf, SHORTS_COLOR, (cx + 9, bottom - 4), (cx + 15, bottom + 8), 8)
        else:  # duck
            pygame.draw.line(surf, SHORTS_COLOR, (cx - 9, bottom - 2), (cx - 13, bottom + 6), 8)
            pygame.draw.line(surf, SHORTS_COLOR, (cx + 9, bottom - 2), (cx + 13, bottom + 6), 8)

        # --- torso ---
        torso_h = int((bottom - top) * 0.68)
        torso_rect = pygame.Rect(cx - w // 2 + 6, bottom - torso_h, w - 12, torso_h)
        pygame.draw.rect(surf, SHIRT_SHADOW, torso_rect.move(0, 3), border_radius=10)
        pygame.draw.rect(surf, SHIRT_COLOR, torso_rect, border_radius=10)

        # --- arms ---
        if pose == "run":
            offset = int(math.sin(ticks * 0.02 + math.pi) * 12)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.left, torso_rect.top + 8),
                              (torso_rect.left - 7, torso_rect.top + 8 + offset), 6)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.right, torso_rect.top + 8),
                              (torso_rect.right + 7, torso_rect.top + 8 - offset), 6)
        elif pose == "jump":
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.left, torso_rect.top + 4),
                              (torso_rect.left - 9, torso_rect.top - 15), 6)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.right, torso_rect.top + 4),
                              (torso_rect.right + 9, torso_rect.top - 15), 6)
        else:  # duck
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.left, torso_rect.top + 6),
                              (torso_rect.left - 11, torso_rect.top + 15), 6)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.right, torso_rect.top + 6),
                              (torso_rect.right + 11, torso_rect.top + 15), 6)

        # --- head ---
        head_r = max(10, int(w * 0.27))
        head_center = (cx, torso_rect.top - head_r + 5)
        pygame.draw.circle(surf, HAIR_COLOR, (head_center[0], head_center[1] - int(head_r * 0.35)), int(head_r * 1.05))
        pygame.draw.circle(surf, SKIN_COLOR, head_center, head_r)


class Obstacle:
    """kind: 'ground' (jump over, styled as a crate) or 'overhead'
    (duck under, styled as a hanging bar)."""

    def __init__(self, lane, kind, y):
        self.lane = lane
        self.kind = kind
        self.y = y
        self.x = LANE_CENTERS[lane]

    @property
    def rect(self):
        if self.kind == "ground":
            return pygame.Rect(self.x - 45, int(self.y) - 34, 90, 34)
        else:  # overhead bar
            return pygame.Rect(self.x - 45, int(self.y) - 92, 90, 24)

    def draw(self, surf):
        rect = self.rect
        if self.kind == "ground":
            pygame.draw.rect(surf, CRATE_COLOR, rect, border_radius=8)
            pygame.draw.rect(surf, CRATE_LIGHT, rect.inflate(-10, -14), border_radius=6)

            # single calm accent band instead of a repeating stripe field --
            # repeating high-contrast stripes in motion are visually fatiguing
            accent_rect = pygame.Rect(rect.left + 6, rect.centery - 3, rect.width - 12, 6)
            pygame.draw.rect(surf, HAZARD_ACCENT, accent_rect, border_radius=3)

            pygame.draw.circle(surf, WHEEL_COLOR, (rect.left + 10, rect.bottom - 2), 6)
            pygame.draw.circle(surf, WHEEL_COLOR, (rect.right - 10, rect.bottom - 2), 6)
        else:
            pygame.draw.rect(surf, POLE_COLOR, (rect.left + 4, rect.top - 40, 6, rect.height + 44))
            pygame.draw.rect(surf, POLE_COLOR, (rect.right - 10, rect.top - 40, 6, rect.height + 44))
            pygame.draw.rect(surf, BAR_COLOR, rect, border_radius=6)
            pygame.draw.rect(surf, BAR_LIGHT, rect.inflate(-10, -8), border_radius=4)


class Coin:
    def __init__(self, lane, y):
        self.lane = lane
        self.y = y
        self.x = LANE_CENTERS[lane]
        self.collected = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 10, int(self.y) - 10, 20, 20)

    def draw(self, surf):
        if self.collected:
            return
        t = pygame.time.get_ticks() * 0.0025 + self.x * 0.05
        pulse = 1.0 + 0.08 * math.sin(t)
        r = max(6, int(10 * pulse))
        pos = (int(self.x), int(self.y))
        pygame.draw.circle(surf, COIN_SHADOW, pos, r + 2)
        pygame.draw.circle(surf, COIN_COLOR, pos, r)
        pygame.draw.circle(surf, COIN_SHINE, (pos[0] - r // 3, pos[1] - r // 3), max(2, r // 3))


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, input_provider: InputProvider):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Subway Clone -- Fitness Build")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18, bold=True)
        self.big_font = pygame.font.SysFont("arial", 44, bold=True)

        self.background = self._build_background()
        self.input_provider = input_provider
        self.reset()

    @staticmethod
    def _build_background():
        """Precomputed vertical gradient, blitted once per frame instead
        of recomputed -- cheap way to make the scene feel less flat."""
        surf = pygame.Surface((WIDTH, HEIGHT))
        top_color = (30, 32, 42)
        bottom_color = (50, 52, 66)
        for y in range(HEIGHT):
            t = y / HEIGHT
            color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
            pygame.draw.line(surf, color, (0, y), (WIDTH, y))
        return surf

    def reset(self):
        self.player = Player()
        self.obstacles = []
        self.coins = []
        self.score = 0.0
        self.time_elapsed = 0.0
        self.game_over = False
        self.spawn_timer = 0.0  # counts down; spawn a row when it hits 0
        self.jump_count = 0
        self.squat_count = 0

    def calories_burned(self):
        return (
            self.jump_count * CAL_PER_JUMP
            + self.squat_count * CAL_PER_SQUAT
            + self.time_elapsed * CAL_PER_SECOND_ACTIVE
        )

    def spawn_row(self):
        lane = random.randint(0, LANE_COUNT - 1)
        kind = random.choice(["ground", "overhead"])
        # Spawn just above the visible screen so obstacles scroll DOWN
        # into view and travel toward the player at the bottom.
        spawn_y = -SPAWN_LEAD_DISTANCE
        self.obstacles.append(Obstacle(lane, kind, spawn_y))

        if random.random() < 0.6:
            coin_lane = random.choice([l for l in range(LANE_COUNT) if l != lane])
            self.coins.append(Coin(coin_lane, spawn_y + 60))

        self.spawn_timer += random.randint(OBSTACLE_MIN_GAP, OBSTACLE_MAX_GAP)

    def current_speed(self):
        # Smooth cycle: BASE -> 2x BASE at the cycle's halfway point ->
        # back to BASE -> repeat. Interval-training pacing, not an
        # endless difficulty ramp.
        progress = (self.time_elapsed % SPEED_CYCLE_SECONDS) / SPEED_CYCLE_SECONDS
        wave = 0.5 * (1 - math.cos(2 * math.pi * progress))
        return BASE_SCROLL_SPEED * (1 + wave * (MAX_SPEED_MULTIPLIER - 1))

    def update(self, events):
        if self.game_over:
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.reset()
            return

        action = self.input_provider.poll(events)
        jumped, ducked = self.player.apply(action)
        if jumped:
            self.jump_count += 1
        if ducked:
            self.squat_count += 1
        self.player.update()

        speed = self.current_speed()
        self.time_elapsed += 1.0 / FPS
        self.score += speed * 0.05

        self.spawn_timer -= speed
        while self.spawn_timer <= 0:
            self.spawn_row()

        for obs in self.obstacles:
            obs.y += speed
        for coin in self.coins:
            coin.y += speed
        self.obstacles = [o for o in self.obstacles if o.y < HEIGHT + 100]
        self.coins = [c for c in self.coins if c.y < HEIGHT + 100]

        player_rect = self.player.rect
        for obs in self.obstacles:
            if player_rect.colliderect(obs.rect):
                avoided = (
                    (obs.kind == "ground" and self.player.jumping)
                    or (obs.kind == "overhead" and self.player.duck_timer > 0)
                )
                same_lane = obs.lane == self.player.lane
                if same_lane and not avoided:
                    self.game_over = True

        for coin in self.coins:
            if not coin.collected and player_rect.colliderect(coin.rect):
                coin.collected = True
                self.score += 25

    def _draw_lane_dashes(self):
        # Static, non-scrolling, low-contrast guide lines -- no motion,
        # no repetition to strobe. Just enough to show lane boundaries.
        for i in range(1, LANE_COUNT):
            x = LANE_WIDTH * i
            line_surf = pygame.Surface((2, HEIGHT), pygame.SRCALPHA)
            line_surf.fill((*LANE_LINE, 70))
            self.screen.blit(line_surf, (x - 1, 0))

    def _draw_hud(self):
        panel = pygame.Surface((WIDTH, 92), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0, 0, 0, 130), panel.get_rect())
        self.screen.blit(panel, (0, 0))

        score_surf = self.font.render(f"Score: {int(self.score)}", True, WHITE)
        self.screen.blit(score_surf, (12, 8))

        intensity_pct = int(
            (self.current_speed() / BASE_SCROLL_SPEED - 1) / (MAX_SPEED_MULTIPLIER - 1) * 100
        )
        intensity_surf = self.font.render(f"Intensity: {intensity_pct}%", True, WHITE)
        self.screen.blit(intensity_surf, (12, 38))

        stats_surf = self.small_font.render(
            f"Jumps: {self.jump_count}   Squats: {self.squat_count}   "
            f"Cal: {self.calories_burned():.1f}",
            True,
            DIM_WHITE,
        )
        self.screen.blit(stats_surf, (12, 68))

    def _draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 165), overlay.get_rect())
        self.screen.blit(overlay, (0, 0))

        over_surf = self.big_font.render("GAME OVER", True, WHITE)
        self.screen.blit(over_surf, over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 150)))

        stats = [
            f"Score: {int(self.score)}",
            f"Jumps: {self.jump_count}",
            f"Squats: {self.squat_count}",
            f"Calories burned: {self.calories_burned():.1f} kcal (approx)",
        ]
        y = HEIGHT // 2 - 80
        for line in stats:
            surf = self.font.render(line, True, WHITE)
            self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))
            y += 36

        hint_surf = self.font.render("Press R to restart", True, DIM_WHITE)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, y + 14)))

    def draw(self):
        self.screen.blit(self.background, (0, 0))
        self._draw_lane_dashes()

        for coin in self.coins:
            coin.draw(self.screen)
        for obs in self.obstacles:
            obs.draw(self.screen)
        self.player.draw(self.screen)

        self._draw_hud()

        if self.game_over:
            self._draw_game_over()

        pygame.display.flip()

    def run(self):
        while True:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            self.update(events)
            self.draw()
            self.clock.tick(FPS)


def main():
    # Swap KeyboardInput() for PoseInput() later -- nothing else changes.
    input_provider = KeyboardInput()
    Game(input_provider).run()


if __name__ == "__main__":
    main()
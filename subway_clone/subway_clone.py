"""
Subway Surfers-style endless runner (Step 2 of the build plan).

Architecture note:
  Game logic never talks to pygame.key directly. It only asks an
  InputProvider for the current action state each frame. Today that's
  KeyboardInput. Later, PoseInput (webcam + MediaPipe) implements the
  exact same interface and gets swapped in with a one-line change in
  main() -- no changes to Game/Player/Obstacle code required.
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
PLAYER_W, PLAYER_H = 50, 70
DUCK_H = 40

GRAVITY = 1.6
JUMP_VELOCITY = -22
DUCK_FRAMES = 28          # how long a duck lasts, in frames

BASE_SCROLL_SPEED = 7.0
SPEED_CYCLE_SECONDS = 30.0   # full slow -> fast -> slow cycle length
MAX_SPEED_MULTIPLIER = 2.0   # peak speed = BASE_SCROLL_SPEED * this

OBSTACLE_MIN_GAP = 480    # min vertical px between spawned obstacles (was 320)
OBSTACLE_MAX_GAP = 700    # (was 520) -- more breathing room between challenges

SPAWN_LEAD_DISTANCE = 120  # px above the screen where obstacles spawn,
                            # before scrolling down into view

FPS = 60

WHITE = (245, 245, 245)
DARK = (25, 25, 30)
LANE_LINE = (60, 60, 70)
PLAYER_COLOR = (60, 170, 255)
GROUND_OBSTACLE_COLOR = (230, 90, 90)   # jump over these
OVERHEAD_OBSTACLE_COLOR = (240, 190, 60)  # duck under these
COIN_COLOR = (250, 220, 80)


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
        top = self.y - h if not self.jumping else self.y - h
        return pygame.Rect(self.x - PLAYER_W // 2, top, PLAYER_W, h)

    def apply(self, action: ActionState):
        if action.move_left and self.lane > 0:
            self.lane -= 1
        if action.move_right and self.lane < LANE_COUNT - 1:
            self.lane += 1
        if action.jump and not self.jumping and self.duck_timer == 0:
            self.jumping = True
            self.vel_y = JUMP_VELOCITY
        if action.duck and not self.jumping and self.duck_timer == 0:
            self.duck_timer = DUCK_FRAMES

    def update(self):
        # smooth lane movement
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
        pygame.draw.rect(surf, PLAYER_COLOR, self.rect, border_radius=8)


class Obstacle:
    """kind: 'ground' (jump over) or 'overhead' (duck under)."""

    def __init__(self, lane, kind, y):
        self.lane = lane
        self.kind = kind
        self.y = y
        self.x = LANE_CENTERS[lane]

    @property
    def rect(self):
        if self.kind == "ground":
            return pygame.Rect(self.x - 45, self.y - 30, 90, 30)
        else:  # overhead bar
            return pygame.Rect(self.x - 45, self.y - 90, 90, 25)

    def draw(self, surf):
        color = GROUND_OBSTACLE_COLOR if self.kind == "ground" else OVERHEAD_OBSTACLE_COLOR
        pygame.draw.rect(surf, color, self.rect, border_radius=6)


class Coin:
    def __init__(self, lane, y):
        self.lane = lane
        self.y = y
        self.x = LANE_CENTERS[lane]
        self.collected = False

    @property
    def rect(self):
        return pygame.Rect(self.x - 10, self.y - 10, 20, 20)

    def draw(self, surf):
        if not self.collected:
            pygame.draw.circle(surf, COIN_COLOR, (self.x, self.y), 10)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, input_provider: InputProvider):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Subway Clone -- Keyboard Build")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 26, bold=True)
        self.big_font = pygame.font.SysFont("arial", 44, bold=True)

        self.input_provider = input_provider
        self.reset()

    def reset(self):
        self.player = Player()
        self.obstacles = []
        self.coins = []
        self.score = 0.0
        self.time_elapsed = 0.0
        self.game_over = False
        self.spawn_timer = 0.0  # counts down; spawn a row when it hits 0
        self.scroll_offset = 0

    def spawn_row(self):
        lane = random.randint(0, LANE_COUNT - 1)
        kind = random.choice(["ground", "overhead"])
        # Spawn just above the visible screen (negative y) so obstacles
        # scroll DOWN into view and travel toward the player at the
        # bottom -- matching how the real game reads (threat approaches
        # from a distance, you watch it coming, you react).
        spawn_y = -SPAWN_LEAD_DISTANCE
        self.obstacles.append(Obstacle(lane, kind, spawn_y))

        # occasionally drop a coin in a different, safe lane
        if random.random() < 0.6:
            coin_lane = random.choice([l for l in range(LANE_COUNT) if l != lane])
            self.coins.append(Coin(coin_lane, spawn_y + 60))

        self.spawn_timer += random.randint(OBSTACLE_MIN_GAP, OBSTACLE_MAX_GAP)

    def current_speed(self):
        # Smooth cycle: 0 -> BASE (slow start), rises to 2x BASE at the
        # halfway point of the cycle, eases back down to BASE, repeats.
        # This gives interval-training pacing (sprint/recover) rather than
        # a game that just keeps getting harder forever.
        progress = (self.time_elapsed % SPEED_CYCLE_SECONDS) / SPEED_CYCLE_SECONDS
        wave = 0.5 * (1 - math.cos(2 * math.pi * progress))  # smoothly 0 -> 1 -> 0
        return BASE_SCROLL_SPEED * (1 + wave * (MAX_SPEED_MULTIPLIER - 1))

    def update(self, events):
        if self.game_over:
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.reset()
            return

        action = self.input_provider.poll(events)
        self.player.apply(action)
        self.player.update()

        speed = self.current_speed()
        self.time_elapsed += 1.0 / FPS
        self.score += speed * 0.05

        # Count down toward the next spawn as the world scrolls; when it
        # hits zero, spawn a new row above the screen and reset the timer.
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

    def draw(self):
        self.screen.fill(DARK)

        for i in range(1, LANE_COUNT):
            x = LANE_WIDTH * i
            pygame.draw.line(self.screen, LANE_LINE, (x, 0), (x, HEIGHT), 2)

        for coin in self.coins:
            coin.draw(self.screen)
        for obs in self.obstacles:
            obs.draw(self.screen)
        self.player.draw(self.screen)

        score_surf = self.font.render(f"Score: {int(self.score)}", True, WHITE)
        self.screen.blit(score_surf, (12, 12))

        intensity_pct = int((self.current_speed() / BASE_SCROLL_SPEED - 1) / (MAX_SPEED_MULTIPLIER - 1) * 100)
        intensity_surf = self.font.render(f"Intensity: {intensity_pct}%", True, WHITE)
        self.screen.blit(intensity_surf, (12, 44))

        if self.game_over:
            over_surf = self.big_font.render("GAME OVER", True, WHITE)
            hint_surf = self.font.render("Press R to restart", True, WHITE)
            self.screen.blit(over_surf, over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
            self.screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30)))

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
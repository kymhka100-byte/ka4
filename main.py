# -*- coding: utf-8 -*-
# 휴대폰용 Kivy 가위바위보 게임
import os
import math
import wave
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.text import LabelBase
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.utils import get_color_from_hex


# ---------------- 기본 설정 ----------------
CHOICES = ["가위", "바위", "보"]
COUNTDOWN = ["가위!", "바위!", "보!"]
WAIT_AFTER_BO = 2.0
AUTO_SECONDS = 3.0
TOTAL_GAMES = 10

# 버튼 색
COLORS = {
    "가위": "#4A90D9",
    "바위": "#43A047",
    "보": "#F39C12",
    "down": "#777777",
    "computer": "#D9534F",
    "player": "#4A90D9",
    "bottom": "#6C63A8",
}


# ---------------- 한글 폰트 ----------------
FONT_CANDIDATES = [
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/NotoSansKR-Regular.otf",
    "/system/fonts/DroidSansFallback.ttf",
]

FONT = None
for p in FONT_CANDIDATES:
    if os.path.exists(p):
        try:
            LabelBase.register(name="Korean", fn_regular=p)
            FONT = "Korean"
            break
        except Exception:
            pass


# ---------------- 클릭 소리 ----------------
def make_click_sound(path):
    rate = 22050
    duration = 0.10
    freq = 880
    frames = int(rate * duration)

    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)

        for i in range(frames):
            t = i / rate
            # 짧게 사라지는 딸깍 소리
            volume = 0.45 * (1 - i / frames)
            value = int(
                32767 * volume * math.sin(2 * math.pi * freq * t)
            )
            f.writeframesraw(
                value.to_bytes(2, "little", signed=True)
            )


def load_click_sound():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "click.wav"
    )
    try:
        if not os.path.exists(path):
            make_click_sound(path)
        return SoundLoader.load(path)
    except Exception:
        return None


# ---------------- 입체 버튼 ----------------
class GameButton(Button):
    def __init__(self, base_hex="#4A90D9", **kwargs):
        super().__init__(**kwargs)
        self.base = get_color_from_hex(base_hex)
        self.down_color = get_color_from_hex(COLORS["down"])
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)

        with self.canvas.before:
            self.shadow_color = Color(0.12, 0.12, 0.12, 0.65)
            self.shadow = RoundedRectangle(radius=[dp(18)])
            self.main_color = Color(*self.base)
            self.main = RoundedRectangle(radius=[dp(18)])
            self.highlight_color = Color(1, 1, 1, 0.22)
            self.highlight = RoundedRectangle(radius=[dp(14)])

        self.bind(pos=self.draw, size=self.draw, state=self.draw)

    def draw(self, *args):
        x, y = self.pos
        w, h = self.size
        down = self.state == "down"

        depth = dp(6)
        self.shadow.pos = (x, y - (0 if down else depth))
        self.shadow.size = (w, h)

        self.main_color.rgba = (
            self.down_color if down else self.base
        )
        self.main.pos = (x, y)
        self.main.size = (w, h - (0 if down else depth))

        self.highlight.pos = (
            x + dp(7),
            y + h - dp(25) - (0 if down else depth),
        )
        self.highlight.size = (max(0, w - dp(14)), dp(13))


# ---------------- 결과 표시 상자 ----------------
class ResultBox(Label):
    def __init__(self, bg_hex, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self.bg_color = Color(*get_color_from_hex(bg_hex))
            self.bg = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size


# ---------------- 게임 ----------------
class RPSGame(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(8),
            **kwargs
        )

        self.round_no = 0
        self.win = 0
        self.lose = 0
        self.draw = 0

        self.waiting = False
        self.result_screen = False
        self.auto_mode = False
        self.selected = None
        self.computer = None
        self.timer_events = []

        self.sound = load_click_sound()
        font = {"font_name": FONT} if FONT else {}

        # 제목
        self.title = Label(
            text="가위바위보",
            font_size=sp(25),
            bold=True,
            size_hint_y=0.08,
            **font
        )
        self.add_widget(self.title)

        # 점수
        self.score = Label(
            text="0 : 0",
            font_size=sp(21),
            bold=True,
            size_hint_y=0.07,
            **font
        )
        self.add_widget(self.score)

        # 메인 메시지
        self.message = Label(
            text="준비하세요",
            font_size=sp(29),
            bold=True,
            halign="center",
            size_hint_y=0.16,
            **font
        )
        self.message.bind(size=self.text_size)
        self.add_widget(self.message)

        # VS 영역
        self.vs_area = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            size_hint_y=0.25,
            opacity=0
        )

        self.computer_box = ResultBox(
            COLORS["computer"],
            text="",
            color=(1, 1, 1, 1),
            font_size=sp(24),
            bold=True,
            **font
        )

        self.vs = Label(
            text="VS",
            font_size=sp(20),
            bold=True,
            size_hint_y=0.20,
            **font
        )

        self.player_box = ResultBox(
            COLORS["player"],
            text="",
            color=(1, 1, 1, 1),
            font_size=sp(24),
            bold=True,
            **font
        )

        self.vs_area.add_widget(self.computer_box)
        self.vs_area.add_widget(self.vs)
        self.vs_area.add_widget(self.player_box)
        self.add_widget(self.vs_area)

        # 확인 / 자동 버튼
        controls = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=0.10
        )
        controls.add_widget(Label(text="", size_hint_x=0.50))

        self.confirm = GameButton(
            COLORS["bottom"],
            text="확인",
            font_size=sp(17),
            bold=True,
            disabled=True,
            size_hint_x=0.25,
            **font
        )
        self.confirm.bind(on_press=self.confirm_result)

        self.auto = GameButton(
            COLORS["bottom"],
            text="자동: OFF",
            font_size=sp(14),
            bold=True,
            size_hint_x=0.25,
            **font
        )
        self.auto.bind(on_press=self.toggle_auto)

        controls.add_widget(self.confirm)
        controls.add_widget(self.auto)
        self.add_widget(controls)

        # 가위 / 바위 / 보
        buttons = GridLayout(
            cols=3,
            spacing=dp(10),
            size_hint_y=0.18
        )

        self.choice_buttons = {}

        for choice in CHOICES:
            b = GameButton(
                COLORS[choice],
                text=choice,
                font_size=sp(24),
                bold=True,
                disabled=True,
                **font
            )
            b.bind(
                on_press=lambda instance, c=choice:
                self.choose(c)
            )
            self.choice_buttons[choice] = b
            buttons.add_widget(b)

        self.add_widget(buttons)

        # 다시 시작
        self.restart = GameButton(
            COLORS["bottom"],
            text="게임 다시 시작",
            font_size=sp(19),
            bold=True,
            size_hint_y=0.10,
            **font
        )
        self.restart.bind(on_press=self.restart_game)
        self.add_widget(self.restart)

        Clock.schedule_once(self.start_round, 1.0)

    def text_size(self, instance, size):
        instance.text_size = (instance.width, None)

    def click(self):
        if self.sound:
            self.sound.stop()
            self.sound.play()

    def cancel_timers(self):
        for event in self.timer_events:
            event.cancel()
        self.timer_events = []

    def later(self, function, seconds):
        event = Clock.schedule_once(
            lambda dt: function(), seconds
        )
        self.timer_events.append(event)

    def start_round(self, *args):
        if self.round_no >= TOTAL_GAMES:
            return

        self.cancel_timers()
        self.waiting = True
        self.result_screen = False
        self.selected = None

        self.vs_area.opacity = 0
        self.confirm.disabled = True

        for b in self.choice_buttons.values():
            b.disabled = False

        self.message.text = COUNTDOWN[0]
        self.later(
            lambda: self.set_message(COUNTDOWN[1]),
            0.7
        )
        self.later(
            lambda: self.set_message(COUNTDOWN[2]),
            1.4
        )
        self.later(self.timeout, 1.4 + WAIT_AFTER_BO)

    def set_message(self, text):
        if self.waiting:
            self.message.text = text

    def choose(self, choice):
        if not self.waiting:
            return

        self.click()
        self.selected = choice
        self.resolve()

    def timeout(self):
        if self.waiting:
            self.message.text = "선택하지 않았어요"
            self.waiting = False

            for b in self.choice_buttons.values():
                b.disabled = True

            self.later(self.start_round, 1.0)

    def resolve(self):
        if not self.waiting:
            return

        self.cancel_timers()
        self.waiting = False

        for b in self.choice_buttons.values():
            b.disabled = True

        self.computer = random.choice(CHOICES)
        result = self.judge(self.selected, self.computer)

        if result == "win":
            self.win += 1
            self.message.text = "승리!"
        elif result == "lose":
            self.lose += 1
            self.message.text = "패배!"
        else:
            self.draw += 1
            self.message.text = "무승부!"

        self.score.text = f"{self.win} : {self.lose}"

        self.round_no += 1
        self.computer_box.text = self.computer
        self.player_box.text = self.selected
        self.vs_area.opacity = 1
        self.result_screen = True
        self.confirm.disabled = False

        if self.auto_mode:
            self.later(self.confirm_result, AUTO_SECONDS)

    def judge(self, player, computer):
        if player == computer:
            return "draw"

        wins = {
            "가위": "보",
            "바위": "가위",
            "보": "바위"
        }

        return "win" if wins[player] == computer else "lose"

    def confirm_result(self, *args):
        if not self.result_screen:
            return

        self.click()
        self.cancel_timers()
        self.result_screen = False
        self.vs_area.opacity = 0
        self.confirm.disabled = True

        if self.round_no >= TOTAL_GAMES:
            self.end_game()
        else:
            self.start_round()

    def toggle_auto(self, *args):
        self.click()
        self.auto_mode = not self.auto_mode
        self.auto.text = (
            "자동: ON" if self.auto_mode else "자동: OFF"
        )

        if self.result_screen and self.auto_mode:
            self.cancel_timers()
            self.later(self.confirm_result, AUTO_SECONDS)

    def end_game(self):
        self.cancel_timers()
        self.waiting = False
        self.result_screen = False
        self.vs_area.opacity = 0
        self.confirm.disabled = True

        self.message.text = "게임 종료!"
        self.title.text = "10판 완료"
        self.score.text = (
            f"최종 점수  {self.win} : {self.lose}"
        )

        for b in self.choice_buttons.values():
            b.disabled = True

    def restart_game(self, *args):
        self.click()
        self.cancel_timers()

        self.round_no = 0
        self.win = 0
        self.lose = 0
        self.draw = 0
        self.waiting = False
        self.result_screen = False
        self.selected = None

        self.title.text = "가위바위보"
        self.score.text = "0 : 0"
        self.message.text = "준비하세요"
        self.vs_area.opacity = 0
        self.confirm.disabled = True

        for b in self.choice_buttons.values():
            b.disabled = True

        self.later(self.start_round, 1.0)


class RPSApp(App):
    def build(self):
        return RPSGame()


if __name__ == "__main__":
    RPSApp().run()

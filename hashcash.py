import pyautogui
import time
 
def move_mouse_and_press_keys():
    screen_width, screen_height = pyautogui.size()
    x, y = screen_width // 2, screen_height // 2
 
    while True:
        # Move mouse to center
        pyautogui.moveTo(x, y, duration=0.2)
        # Press up key
        pyautogui.press('up')
        time.sleep(10)
        # Press down key
        pyautogui.press('down')
        time.sleep(10)
 
if __name__ == "__main__":
    print("Press Ctrl+C to stop.")
    move_mouse_and_press_keys()
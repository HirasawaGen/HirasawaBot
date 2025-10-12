import cv2
from cv2.typing import MatLike

import numpy as np
import random


def obfuscation(img: MatLike) -> MatLike:
    w, h, c = img.shape
    new_w = w * 5 // 4
    new_h = h * 5 // 4
    diff_w = new_w - w
    diff_h = new_h - h
    w_start = random.randint(0, diff_w)
    h_start = random.randint(0, diff_h)
    pixel_num = w * h
    choice = random.randint(0, 1)
    if choice == 0:
        img = cv2.flip(img, 0)
    choice = random.randint(0, 1)
    if choice == 0:
        img = cv2.flip(img, 1)
    for _ in range(pixel_num // 32):
        noise = np.random.randint(-25, 25, (c,), dtype=np.int8)
        p_w = random.randint(1, w-2)
        p_h = random.randint(1, h-2)
        img[p_w, p_h] = (img[p_w+1, p_h] + img[p_w-1, p_h] + img[p_w, p_h+1] + img[p_w, p_h-1]) // 4 + noise
    new_img = np.random.randint(0, 256, (new_w, new_h, c), dtype=np.uint8)
    new_img[w_start:w_start+w, h_start:h_start+h] = img
    return new_img


if __name__ == '__main__':
    img = cv2.imread('test.webp')
    new_img = obfuscation(img)
    cv2.imwrite('new_test.webp', new_img)
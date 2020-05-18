import mss
import cv2
import numpy as np
import time
import os

sct = mss.mss()
# Part of the screen to capture: try numpy slicing to improve performance
tokens_rect = {"top": 450, "left": 700, "width": 550, "height": 160}
damage_rect = {"top": 725, "left": 810, "width": 100, "height": 45}
accuracy_rect = {"top": 725, "left": 960, "width": 130, "height": 45}

MEDIA_ROOT = 'media/'
NUMBERS_ROOT = MEDIA_ROOT + 'numbers/'


def check_similarity(image1, image2):
    return cv2.matchTemplate(image1, image2, cv2.TM_CCORR)[0][0]


def classify_digit(image):
    max_confidence = 0
    number = -1
    for filename in os.listdir(NUMBERS_ROOT):
        confidence = check_similarity(image, cv2.imread(NUMBERS_ROOT + filename, cv2.IMREAD_GRAYSCALE))
        if confidence > max_confidence:
            max_confidence = confidence
            try:
                filename = filename.split('_')[0].split('.')[0]
                number = int(filename)
            except ValueError:
                number = -1

    return number


def find_template_in_image(image, template):
    processed = cv2.matchTemplate(image, template, cv2.TM_CCORR)
    max_loc = cv2.minMaxLoc(processed)[3]
    return max_loc


def remove_template_from_image(image, template):
    template_position = find_template_in_image(image, template)
    x = template_position[0]
    return image[:, :x]


def preprocess_image(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image = cv2.GaussianBlur(image, (3, 3), 0)
    _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return image


def resize_roi(roi):
    roi = cv2.resize(roi, (22, 22))
    roi = 255 - roi
    roi = cv2.copyMakeBorder(roi, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=0)
    roi = np.reshape(roi, (28, 28, 1))
    return roi


def extract_components(image):
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(image, connectivity=8)
    roi_list = []
    for label in range(1, n_labels):
        width = stats[label, cv2.CC_STAT_WIDTH]
        height = stats[label, cv2.CC_STAT_HEIGHT]
        x = stats[label, cv2.CC_STAT_LEFT]
        y = stats[label, cv2.CC_STAT_TOP]
        roi = labels[y - 1:y + height + 1,
              x - 1:x + width + 1].copy()  # create a copy of the interest region from the labeled image
        roi[roi != label] = 255  # set the other labels to white to eliminate intersections with other labels
        roi[roi == label] = 0  # set the interest region to black

        roi = np.array(roi, dtype=np.uint8)
        if roi.size > 0:
            roi = resize_roi(roi)
            roi_list.append(roi)
    return roi_list


def remove_percentage(image):
    percentage_image = cv2.imread(MEDIA_ROOT + 'percentage.png', cv2.IMREAD_GRAYSCALE)
    image = remove_template_from_image(image, percentage_image)
    return image


def extract_digits(image, additional_preprocessing=None):
    image = preprocess_image(image)

    if additional_preprocessing:
        image = additional_preprocessing(image)

    return extract_components(image)


def read_number_from_digit_images(digit_list):
    if len(digit_list) > 0:
        num = 0
        i = 0
        for digit_image in digit_list[::-1]:
            digit = classify_digit(digit_image)
            if digit != -1:
                num += digit * 10 ** i
                i += 1
        return num


count = 0


def debug_view_rois(rois, num, screen_name, save_character):
    global count

    white = np.full((28, 28, 1), 255, dtype=np.uint8)
    img = cv2.vconcat([white] + rois)
    img = cv2.putText(img, str(num), (0, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0))
    cv2.imshow(screen_name, img)
    print(num)
    if cv2.waitKey(25) & 0xFF == ord(save_character):
        for roi in rois:
            cv2.imwrite(f"number_{count}.png", roi)
            count += 1


while "Screen capturing":
    last_time = time.time()

    # Get raw pixels from the screen, save it to a Numpy array
    accuracy_image = np.array(sct.grab(accuracy_rect))
    damage_image = np.array(sct.grab(damage_rect))
    tokens_image = np.array(sct.grab(tokens_rect))

    # preprocess accuracy_image
    roi_list = extract_digits(accuracy_image, additional_preprocessing=remove_percentage)
    num = read_number_from_digit_images(roi_list)
    debug_view_rois(roi_list, num, "accuracy", "s")  # debug

    # preprocess damage_image
    damage_rois = extract_digits(damage_image)
    damage_num = read_number_from_digit_images(damage_rois)
    debug_view_rois(damage_rois, damage_num, "damage", "p")  # debug

    print("fps: {}".format(1 / (time.time() - last_time)))

    # Press "q" to quit
    if cv2.waitKey(25) & 0xFF == ord("q"):
        cv2.destroyAllWindows()
        break

import json
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset
import torchvision.transforms as transforms
from random import shuffle
import cv2
import time

def process_img(img):
    means = [0.485, 0.456, 0.406]
    inv_stds = [1/0.229, 1/0.224, 1/0.225]

    img = Image.fromarray(img)
    img = transforms.ToTensor()(img)
    for channel, mean, inv_std in zip(img, means, inv_stds):
        channel.sub_(mean).mul_(inv_std)
    return img

def aug(img):
    return transforms.RandomHorizontalFlip(p=0.5)(
        transforms.ColorJitter(contrast=0.25)(
            transforms.RandomAffine(
                0, translate=(0.03, 0.03))(img)))


categories = ['airplane', 'apple', 'backpack', 'banana', 'baseball bat',
              'baseball glove', 'bear', 'bed', 'bench', 'bicycle', 'bird',
              'boat', 'book', 'bottle', 'bowl', 'broccoli', 'bus', 'cake',
              'car', 'carrot', 'cat', 'cell phone', 'chair', 'clock', 'couch',
              'cow', 'cup', 'dining table', 'dog', 'donut', 'elephant',
              'fire hydrant', 'fork', 'frisbee', 'giraffe', 'hair drier',
              'handbag', 'horse', 'hot dog', 'keyboard', 'kite', 'knife',
              'laptop', 'microwave', 'motorcycle', 'mouse', 'orange', 'oven',
              'parking meter', 'person', 'pizza', 'potted plant', 'refrigerator',
              'remote', 'sandwich', 'scissors', 'sheep', 'sink', 'skateboard',
              'skis', 'snowboard', 'spoon', 'sports ball', 'stop sign', 'suitcase',
              'surfboard', 'teddy bear', 'tennis racket', 'tie', 'toaster', 'toilet',
              'toothbrush', 'traffic light', 'train', 'truck', 'tv', 'umbrella', 'vase',
              'wine glass', 'zebra']
categories_sorted_by_freq = ['person', 'chair', 'car', 'dining table', 'cup',
                             'bottle', 'bowl', 'handbag', 'truck', 'backpack',
                             'bench', 'book', 'cell phone', 'sink', 'tv', 'couch',
                             'clock', 'knife', 'potted plant', 'dog', 'sports ball',
                             'traffic light', 'cat', 'bus', 'umbrella', 'tie', 'bed',
                             'fork', 'vase', 'skateboard', 'spoon', 'laptop',
                             'train', 'motorcycle', 'tennis racket', 'surfboard',
                             'toilet', 'bicycle', 'airplane', 'bird', 'skis', 'pizza',
                             'remote', 'boat', 'cake', 'horse', 'oven', 'baseball glove',
                             'baseball bat', 'giraffe', 'wine glass', 'refrigerator',
                             'sandwich', 'suitcase', 'kite', 'banana', 'elephant',
                             'frisbee', 'teddy bear', 'keyboard', 'cow', 'broccoli', 'zebra',
                             'mouse', 'orange', 'stop sign', 'fire hydrant', 'carrot',
                             'apple', 'snowboard', 'sheep', 'microwave', 'donut', 'hot dog',
                             'toothbrush', 'scissors', 'bear', 'parking meter', 'toaster',
                             'hair drier']
categories_sorted_by_freq = dict((x, len(categories) - count)
                                 for count, x in enumerate(categories_sorted_by_freq))
category_dict_classification = dict((category, count) for count, category in enumerate(categories))
category_dict_sequential = dict((category, count) for count, category in enumerate(categories))
category_dict_sequential['<end>'] = len(categories)
category_dict_sequential['<start>'] = len(categories) + 1
category_dict_sequential['<pad>'] = len(categories) + 2
category_dict_sequential_inv = dict((value, key)
                                    for key, value in category_dict_sequential.items())

class COCOMultiLabel(Dataset):
    def __init__(self, train, classification, img_path, sort_by_freq=False):
        super(COCOMultiLabel, self).__init__()
        self.train = train
        if self.train == True:
            self.coco_json = json.load(open('coco_train.json', 'r'))
            self.max_length = 18 + 2 # highest number of labels for one img in training
            self.img_path = img_path + '/train2014/'
        elif self.train == False:
            self.coco_json = json.load(open('coco_val.json', 'r'))
            self.max_length = 15 + 2
            self.img_path = img_path + '/val2014/'

        else:
            assert 0 == 1
        assert classification in [True, False]
        self.classification = classification
        self.fns = self.coco_json.keys()
        self.sort_by_freq = sort_by_freq
        if self.sort_by_freq:
            print('Sorting by frequency')

    def __len__(self):
        return len(self.coco_json)

    def __getitem__(self, idx):
        j_key = self.fns[idx]
        ctg_batch = self.coco_json[j_key]['categories']
        img_fn = self.img_path + j_key

        img = Image.open(img_fn)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        if self.train:
            try:
                img = aug(img)
            except IOError:
                print ('augmentation error')
        transform=transforms.Compose([
                           transforms.Resize((288, 288)),
                           transforms.ToTensor(),
                           transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                                std=[0.229, 0.224, 0.225])
                           ])
        try:
            img = transform(img)        
        except IOError:
            return None

        # labels
        labels_freq_indexes = [categories_sorted_by_freq[x] for x in ctg_batch]
        labels = []
        labels_classification = np.zeros(len(categories), dtype=np.float32)
        labels.append(category_dict_sequential['<start>'])
        for category in ctg_batch:
            labels.append(category_dict_sequential[category])
            labels_classification[category_dict_classification[category]] = 1

        if self.sort_by_freq:
            labels_new = [category_dict_sequential['<start>']]
            labels_new.extend([label
                               for _, label in sorted(zip(labels_freq_indexes, labels[1:]), reverse=True)])
            labels = labels_new[:]

        labels.append(category_dict_sequential['<end>'])
        for _ in range(self.max_length - len(ctg_batch) - 1):
            labels.append(category_dict_sequential['<pad>'])

        labels = torch.LongTensor(labels)
        labels_classification = torch.from_numpy(labels_classification)
        label_number = len(ctg_batch) + 2 # including the <start> and <end>

        if self.classification:
            return_tuple = (img, labels_classification)
        else:
            return_tuple = (img, labels, label_number, labels_classification)
        return return_tuple

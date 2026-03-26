from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor
# from mobile_sam import SamAutomaticMaskGenerator
import torch
import cv2
import numpy as np
import matplotlib.pyplot as plt


def show_mask(img, mask, random_color=False):
    '''
    Modifying the original code to 
        Show mask on image.
        Save the segmented image.
    '''
    if random_color:
        color = np.concatenate([np.random.random(3), np.array([0.6])], axis=0)
    else:
        color = np.array([30/255, 144/255, 255/255, 0.6])
    h, w = mask.shape[-2:]
    # mask_image = mask.reshape(h, w, 1) * color.reshape(1, 1, -1)

    # mask = mask.reshape(mask.shape[1], mask.shape[2], mask.shape[0])
    # mask = np.repeat(mask,3,axis=2)
    # mask_overlay = np.zeros((h, w, 3), dtype=np.uint8)
    # mask_overlay[mask] = color
    # segmented_image = cv2.addWeighted(img, 0.7, mask_overlay, 0.3, 0)

    color = np.array([255, 0, 255], dtype=np.uint8)
    h, w = mask.shape[-2:]
    mask_overlay = np.zeros((h, w, 3), dtype=np.uint8)
    mask = mask.reshape(h, w)
    mask_overlay[mask] = color
    segmented_image = cv2.addWeighted(img, 1.0, mask_overlay, 0.2, 0)
    #segmented_image = np.where(mask.reshape(h, w)[..., None], color, img)
    
    # Return the final image (in BGR format for cv2.imwrite)
    return cv2.cvtColor(segmented_image, cv2.COLOR_RGB2BGR)

def segmentation_(imgs_path, coords):
    model_type = "vit_t"
    sam_checkpoint = r"D:\courses-2025\prototype\SegInference\weights\mobile_sam.pt"

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(device)

    mobile_sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
    mobile_sam.to(device=device)
    mobile_sam.eval()

    img_path = imgs_path
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    #cv2.imwrite(img_path, segmented_image)

    #random coord
    coord = coords
    coord_x=[]
    coord_y=[]
    for Ditem in coord[0]:
            coord_x.append(int(Ditem['x']))
            coord_y.append(int(Ditem['y']))

    xmin, xmax = min(coord_x), max(coord_x)
    ymin, ymax = min(coord_y), max(coord_y)

    #xmin, ymin, xmax, ymax = xmin*3, ymin*3, xmax*3, ymax*3
    h, w = img.shape[0], img.shape[1]
    hh, ww = h/392, w/350
    print(hh, ww)

    xmin, ymin, xmax, ymax = xmin*ww, ymin*hh, xmax*ww, ymax*hh
    input_box = np.array([xmin, ymin, xmax, ymax])
    input_point = np.array([[int((xmax-xmin)/2)+xmin, int((ymax-ymin)/2)+ymin]])
    input_label = np.array([1])

    predictor = SamPredictor(mobile_sam)
    predictor.set_image(img)
    masks, scores, logits = predictor.predict(
        point_coords=input_point,
        point_labels=input_label,
        box=input_box[None, :],
        multimask_output=False,
    )

    # mask_generator = SamAutomaticMaskGenerator(mobile_sam)
    # masks = mask_generator.generate(<your_image>)

    # print(masks)

    # masks_ = masks.reshape(masks.shape[1], masks.shape[2], masks.shape[0])

    segmented_image = show_mask(img, masks)
    cv2.imwrite(img_path.split('.')[0]+'_seg.png', segmented_image)

    return segmented_image
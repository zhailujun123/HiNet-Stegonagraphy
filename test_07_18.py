import math
import torch
import torch.nn
import torch.optim
import torchvision
import numpy as np
from model import *
import config as c
import datasets
import modules.Unet_common as common
import matplotlib.pyplot as plt
from PIL import Image
import torchvision.transforms as transforms

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def load(name):
    state_dicts = torch.load(name)
    network_state_dict = {k:v for k,v in state_dicts['net'].items() if 'tmp_var' not in k}
    net.load_state_dict(network_state_dict)
    try:
        optim.load_state_dict(state_dicts['opt'])
    except:
        print('Cannot load optimizer for some reason or other')


def gauss_noise(shape):

    noise = torch.zeros(shape).cuda()
    for i in range(noise.shape[0]):
        noise[i] = torch.randn(noise[i].shape).cuda()

    return noise


def computePSNR(origin,pred):
    origin = np.array(origin)
    origin = origin.astype(np.float32)
    pred = np.array(pred)
    pred = pred.astype(np.float32)
    mse = np.mean((origin/1.0 - pred/1.0) ** 2 )
    if mse < 1.0e-10:
      return 100
    return 10 * math.log10(255.0**2/mse)


net = Model()
net.cuda()
init_model(net)
net = torch.nn.DataParallel(net, device_ids=c.device_ids)
params_trainable = (list(filter(lambda p: p.requires_grad, net.parameters())))
optim = torch.optim.Adam(params_trainable, lr=c.lr, betas=c.betas, eps=1e-6, weight_decay=c.weight_decay)
weight_scheduler = torch.optim.lr_scheduler.StepLR(optim, c.weight_step, gamma=c.gamma)

load(c.MODEL_PATH + c.suffix)

net.eval()

dwt = common.DWT()
iwt = common.IWT()


with torch.no_grad():
    for i, data in enumerate(datasets.testloader):
        data = data.to(device)
        cover = data[data.shape[0] // 2:, :, :, :]
        secret = data[:data.shape[0] // 2, :, :, :]
        cover_input = dwt(cover)
        secret_input = dwt(secret)
        input_img = torch.cat((cover_input, secret_input), 1)

        #################
        #    forward:   #
        #################
        output = net(input_img)
        output_steg = output.narrow(1, 0, 4 * c.channels_in)
        print("0 output_steg.shape is:", output_steg.shape)
        output_z = output.narrow(1, 4 * c.channels_in, output.shape[1] - 4 * c.channels_in)
        steg_img = iwt(output_steg)
        print("1 net steg_img.shape ", steg_img.shape)
        #################Lujun For deep fake attack only : Run this file without image.open first. Then replace stego image with deep fake image  and empty secret image foler. THEN re-run this file
        image_path = "/home/cui/HiNet-main/image/steg_deepfake/d.jpg"
        steg_img = Image.open(image_path)  #Image.open(image_path)
        # #Apply the ToTensor transformation
        transform = transforms.ToTensor()
        steg_img_tensor = transform(steg_img)
        steg_img = steg_img_tensor.unsqueeze(0)  #reshaped_tensor 
        print("2 deepfake steg img.shape is ", steg_img.shape)
        ################################################################################################
        ################################################################################################
        
        backward_z = gauss_noise(output_z.shape)
        print("3 backward_z ", backward_z.shape)
        #################
        #   backward:   #
        #################
        #output_rev = torch.cat((output_steg, backward_z), 1)     # use net generated steg img     
        output_rev = torch.cat((dwt(steg_img).to('cuda:0'), backward_z), 1)  # Use deepfake steg img 
        
        bacward_img = net(output_rev, rev=True)
        secret_rev = bacward_img.narrow(1, 4 * c.channels_in, bacward_img.shape[1] - 4 * c.channels_in)
        secret_rev = iwt(secret_rev)
        cover_rev = bacward_img.narrow(1, 0, 4 * c.channels_in)
        cover_rev = iwt(cover_rev)
        steg_img = steg_img.to('cuda:0')  # Move `steg_img` to the CUDA device
        cover = cover.to('cuda:0')  # Move `cover` to the CUDA device
        resi_cover = (steg_img - cover) * 20
        resi_secret = (secret_rev - secret) * 20

        torchvision.utils.save_image(cover, c.IMAGE_PATH_cover + '%.5d.png' % i)
        torchvision.utils.save_image(secret, c.IMAGE_PATH_secret + '%.5d.png' % i)
        #torchvision.utils.save_image(steg_img, c.IMAGE_PATH_steg + '%.5d.png' % i)
        torchvision.utils.save_image(secret_rev, c.IMAGE_PATH_secret_rev + '%.5d.png' % i)
        torchvision.utils.save_image(cover_rev, '/home/cui/HiNet-main/image/cover_rev/'+ '%.5d.png' % i)
        torchvision.utils.save_image(resi_cover, '/home/cui/HiNet-main/image/resi_cover/'+ '%.5d.png' % i)
        torchvision.utils.save_image(resi_secret, '/home/cui/HiNet-main/image/resi_secret/'+ '%.5d.png' % i)




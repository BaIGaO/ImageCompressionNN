import torch.nn as nn
import numpy as np
import torch
import math


class Net(nn.Module):

    def __init__(self):
        super(Net, self).__init__()

        self.encoder = Encoder()
        self.decoder = Decoder()

    def forward(self, img, encode=True):

        if encode:
            return self.encoder(img)
        else:
            return self.decoder(img)


class Encoder(nn.Module):


    def __init__(self):

        super(Encoder, self).__init__()

        self.scales = 6
        self.alignment_scale = (32, 32)

        # decomposition layer
        self.decompLayer = nn.Sequential(nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1),
                                         nn.LeakyReLU(0.2),
                                         nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1),
                                         nn.LeakyReLU(0.2),
                                         nn.BatchNorm2d(64))

        # interscale alignment layer
        self.downsampleLayers = {
            8: nn.Conv2d(64, 64, kernel_size=3, stride=8, padding=1),
            4: nn.Conv2d(64, 64, kernel_size=3, stride=4, padding=1),
            2: nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1),
            1: nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1)
        }

        self.upsampleLayers = {
            2: nn.ConvTranspose2d(64, 64, kernel_size=3, stride=2, padding=1),
            4: nn.ConvTranspose2d(64, 64, kernel_size=3, stride=4, padding=1)
        }

        # output layer
        self.outputLayer = nn.Sequential(nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1),
                                         nn.LeakyReLU(0.2),
                                         nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1),
                                         nn.LeakyReLU(0.2))

        self.scale_factor = 0.5
        self.coef_maps = list()


    def decompose(self, xm, size):
        """
        Performs pyramidal decomposition by extracting
        coefficients from the input scale and computing next scale.

        :param xm: Tensor for image
        :param size: tuple of height and width desired in interpolation
        :return: Tensor for coefficient and Tensor for downsampled image
        """

        # downsample to next scale
        xm1 = nn.functional.interpolate(xm, mode='bilinear', size=size)
        xm = self.decompLayer(xm)

        # return coefficiant and downsampled image
        return xm, xm1


    def align(self):
        """
            Performs interscale alignment of features in the
            coef_map. Computes difference between size of coef tensor
            and alignment_scale then passes coef through appropriate
            conv layer. coef_map must contain a tensor for each scale.

            :returns Tensor for sum of coefficients
        """
        # len(self.coef_maps) == self.scales
        print(len(self.coef_maps))

        # sum of coefficient tensors
        y = torch.zeros(size=(32, 32, 64), dtype=torch.float32)

        for coef in self.coef_maps:

            # dimensions of coef tensor and desired alignment
            align_scale = self.alignment_scale
            coef_scale = tuple(coef.size())

            # determine which conv to pass img through
            if coef_scale > self.alignment_scale:
                conv = self.downsampleLayers[int(coef_scale[0] / align_scale[0])]
            else:

                print(coef_scale)
                conv = self.upsampleLayers[int(align_scale[0] / coef_scale[0])]

            # align coefficients
            y += conv(coef)

        return y


    def forward(self, x):
        """
            :param x Tensor for Image that will be compressed
            :returns Tensor for compressed image
        """

        xm = x
        dimensions = np.array([256.0, 256.0])

        # perform pyramidal decomposition
        for scale in range(self.scales):
            x, xm = self.decompose(xm, tuple(map(lambda x: int(x), dimensions)))
            self.coef_maps.append(x)
            dimensions *= self.scale_factor


        # perform interscale alignment
        y = self.align()

        # convolve aligned features
        y = self.outputLayer(y)

        # compressed image
        return y


class Quantization(nn.Module):

    B = 6

    def __init__(self):
        super(Quantization, self).__init__()

    def forward(self, y):
        return (1 / pow(2, self.B - 1)) * math.ceil(pow(2, self.B - 1) * y)


class Decoder(nn.Module):

    def __init__(self):
        super(Decoder, self).__init__()

        self.layer1 = nn.Sequential(nn.ConvTranspose2d(64, 64, kernel_size=3, stride=8, padding=1), nn.LeakyReLU(0.2))
        self.layer2 = nn.Sequential(nn.ConvTranspose2d(64, 64, kernel_size=3, stride=8, padding=1), nn.LeakyReLU(0.2))
        self.layer3 = nn.Sequential(nn.ConvTranspose2d(64, 64, kernel_size=3, stride=8, padding=1), nn.LeakyReLU(0.2))
        self.layer4 = nn.Sequential(nn.ConvTranspose2d(64, 64, kernel_size=3, stride=8, padding=1), nn.LeakyReLU(0.2))


    def forward(self, img):
        """

        :param img: 32x32 compressed image
        :return: 256X256 reconstructed image
        """


        img = self.layer1(img)
        img = nn.functional.interpolate(img, mode="bilinear", size=(64, 64, 64))
        img = self.layer2(img)
        img = nn.functional.interpolate(img, mode="bilinear", size=(128, 128, 64))
        img = self.layer3(img)
        img = nn.functional.interpolate(img, mode="bilinear", size=(256, 256, 64))
        img = self.layer4(img)

        return img
    
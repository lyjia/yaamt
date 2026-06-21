"""
KeyNet CNN model for musical key classification.

Originally from the MusicalKeyCNN project (references/MusicalKeyCNN/model.py).
Copied here so that PyInstaller can discover it as a normal module import,
avoiding the sys.path manipulation needed to reach the references/ directory
which is not included in compiled builds.
"""

import torch.nn as nn


class BasicConv2d(nn.Module):
    """
    Basic convolutional block: Conv2d -> BatchNorm2d -> ELU.
    """
    def __init__(self, in_channels, out_channels, kernel_size):
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            padding='same',
            bias=False
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.elu = nn.ELU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.elu(x)
        return x


class KeyNet(nn.Module):
    """
    CNN for musical key classification (Korzeniowski & Widmer, 2018).

    Outputs logits for 24 key classes (12 tonic x {major, minor}).
    """
    def __init__(self, num_classes=24, in_channels=1, Nf=20, p=0.5):
        super().__init__()

        self.conv1 = BasicConv2d(in_channels, Nf, kernel_size=5)
        self.conv2 = BasicConv2d(Nf, Nf, kernel_size=3)
        self.pool1 = nn.MaxPool2d(2)
        self.dropout1 = nn.Dropout2d(p=p)

        self.conv3 = BasicConv2d(Nf, 2*Nf, kernel_size=3)
        self.conv4 = BasicConv2d(2*Nf, 2*Nf, kernel_size=3)
        self.pool2 = nn.MaxPool2d(2)
        self.dropout2 = nn.Dropout2d(p=p)

        self.conv5 = BasicConv2d(2*Nf, 4*Nf, kernel_size=3)
        self.conv6 = BasicConv2d(4*Nf, 4*Nf, kernel_size=3)
        self.pool3 = nn.MaxPool2d(2)
        self.dropout3 = nn.Dropout2d(p=p)

        self.conv7 = BasicConv2d(4*Nf, 8*Nf, kernel_size=3)
        self.dropout4 = nn.Dropout2d(p=p)
        self.conv8 = BasicConv2d(8*Nf, 8*Nf, kernel_size=3)
        self.dropout5 = nn.Dropout2d(p=p)

        self.conv9 = BasicConv2d(8*Nf, num_classes, kernel_size=1)
        self.global_avgpool = nn.AdaptiveAvgPool2d((1, 1))

    def forward(self, x):
        import torch

        x = self.conv1(x)
        x = self.conv2(x)
        x = self.pool1(x)
        x = self.dropout1(x)

        x = self.conv3(x)
        x = self.conv4(x)
        x = self.pool2(x)
        x = self.dropout2(x)

        x = self.conv5(x)
        x = self.conv6(x)
        x = self.pool3(x)
        x = self.dropout3(x)

        x = self.conv7(x)
        x = self.dropout4(x)
        x = self.conv8(x)
        x = self.dropout5(x)
        x = self.conv9(x)

        x = self.global_avgpool(x)
        x = torch.flatten(x, 1)
        return x

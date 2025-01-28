#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2009 Kazuhiko Arase (http://www.d-project.com/)
#               2010 Bulia Byak <buliabyak@gmail.com>
#               2018 Kirill Okhotnikov <kirill.okhotnikov@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110, USA.
#
"""
Provide the QR Code rendering.
"""

from __future__ import print_function

from itertools import product
from collections import defaultdict

import numpy as np

import inkex
from inkex import Group, Rectangle, Use, PathElement
from inkex.paths import Move, zoneClose, Line, Curve
from inkex.localization import inkex_gettext as _
from inkex.utils import circular_pairwise


class QRLengthError(Exception):
    def __init__(self, message):
        self.message = message


class QRCode(object):
    PAD0 = 0xEC
    PAD1 = 0x11

    def __init__(self, correction):
        self.typeNumber = 1
        self.errorCorrectLevel = correction
        self.qrDataList = []
        self.modules = []
        self.moduleCount = 0

    def getTypeNumber(self):
        return self.typeNumber

    def setTypeNumber(self, typeNumber):
        self.typeNumber = typeNumber

    def clearData(self):
        self.qrDataList = []

    def addData(self, data):
        self.qrDataList.append(data)

    def getDataCount(self):
        return len(self.qrDataList)

    def getData(self, index):
        return self.qrDataList[index]

    def isDark(self, row, col):
        return self.modules[row][col] if self.modules[row][col] is not None else False

    def getModuleCount(self):
        return self.moduleCount

    def make(self):
        self._make(False, self._getBestMaskPattern())

    def _getBestMaskPattern(self):
        minLostPoint = 0
        pattern = 0
        for i in range(8):
            self._make(True, i)
            lostPoint = QRUtil.getLostPoint(self)
            if i == 0 or minLostPoint > lostPoint:
                minLostPoint = lostPoint
                pattern = i
        return pattern

    def _make(self, test, maskPattern):
        self.moduleCount = self.typeNumber * 4 + 17
        self.modules = np.array(
            [[None] * self.moduleCount for i in range(self.moduleCount)]
        )

        self._setupPositionProbePattern(0, 0)
        self._setupPositionProbePattern(self.moduleCount - 7, 0)
        self._setupPositionProbePattern(0, self.moduleCount - 7)

        self._setupPositionAdjustPattern()
        self._setupTimingPattern()

        self._setupTypeInfo(test, maskPattern)

        if self.typeNumber >= 7:
            self._setupTypeNumber(test)

        data = QRCode._createData(
            self.typeNumber, self.errorCorrectLevel, self.qrDataList
        )

        self._mapData(data, maskPattern)

    def _mapData(self, data, maskPattern):
        rows = list(range(self.moduleCount))
        cols = [
            col - 1 if col <= 6 else col for col in range(self.moduleCount - 1, 0, -2)
        ]
        maskFunc = QRUtil.getMaskFunction(maskPattern)

        byteIndex = 0
        bitIndex = 7

        for col in cols:
            rows.reverse()
            for row in rows:
                for c in range(2):
                    if self.modules[row][col - c] is None:
                        dark = False
                        if byteIndex < len(data):
                            dark = ((data[byteIndex] >> bitIndex) & 1) == 1
                        if maskFunc(row, col - c):
                            dark = not dark
                        self.modules[row][col - c] = dark

                        bitIndex -= 1
                        if bitIndex == -1:
                            byteIndex += 1
                            bitIndex = 7

    def _setupPositionAdjustPattern(self):
        pos = QRUtil.getPatternPosition(self.typeNumber)
        for row in pos:
            for col in pos:
                if self.modules[row][col] is not None:
                    continue
                for r in range(-2, 3):
                    for c in range(-2, 3):
                        self.modules[row + r][col + c] = (
                            r == -2
                            or r == 2
                            or c == -2
                            or c == 2
                            or (r == 0 and c == 0)
                        )

    def _setupPositionProbePattern(self, row, col):
        for r in range(-1, 8):
            for c in range(-1, 8):
                if (
                    row + r <= -1
                    or self.moduleCount <= row + r
                    or col + c <= -1
                    or self.moduleCount <= col + c
                ):
                    continue
                self.modules[row + r][col + c] = (
                    (0 <= r <= 6 and (c == 0 or c == 6))
                    or (0 <= c <= 6 and (r == 0 or r == 6))
                    or (2 <= r <= 4 and 2 <= c <= 4)
                )

    def _setupTimingPattern(self):
        for r in range(8, self.moduleCount - 8):
            if self.modules[r][6] is not None:
                continue
            self.modules[r][6] = r % 2 == 0
        for c in range(8, self.moduleCount - 8):
            if self.modules[6][c] is not None:
                continue
            self.modules[6][c] = c % 2 == 0

    def _setupTypeNumber(self, test):
        bits = QRUtil.getBCHTypeNumber(self.typeNumber)
        for i in range(18):
            self.modules[i // 3][i % 3 + self.moduleCount - 8 - 3] = (
                not test and ((bits >> i) & 1) == 1
            )
        for i in range(18):
            self.modules[i % 3 + self.moduleCount - 8 - 3][i // 3] = (
                not test and ((bits >> i) & 1) == 1
            )

    def _setupTypeInfo(self, test, maskPattern):
        data = (self.errorCorrectLevel << 3) | maskPattern
        bits = QRUtil.getBCHTypeInfo(data)

        # vertical
        for i in range(15):
            mod = not test and ((bits >> i) & 1) == 1
            if i < 6:
                self.modules[i][8] = mod
            elif i < 8:
                self.modules[i + 1][8] = mod
            else:
                self.modules[self.moduleCount - 15 + i][8] = mod

        # horizontal
        for i in range(15):
            mod = not test and ((bits >> i) & 1) == 1
            if i < 8:
                self.modules[8][self.moduleCount - i - 1] = mod
            elif i < 9:
                self.modules[8][15 - i - 1 + 1] = mod
            else:
                self.modules[8][15 - i - 1] = mod

        # fixed
        self.modules[self.moduleCount - 8][8] = not test

    @staticmethod
    def _createData(typeNumber, errorCorrectLevel, dataArray):
        rsBlocks = RSBlock.getRSBlocks(typeNumber, errorCorrectLevel)

        buffer = BitBuffer()

        for data in dataArray:
            buffer.put(data.getMode(), 4)
            buffer.put(data.getLength(), data.getLengthInBits(typeNumber))
            data.write(buffer)

        totalDataCount = sum(rsBlock.getDataCount() for rsBlock in rsBlocks)

        if buffer.getLengthInBits() > totalDataCount * 8:
            raise QRLengthError(
                "code length overflow. (%s>%s)"
                % (buffer.getLengthInBits(), totalDataCount * 8)
            )

        # end code
        if buffer.getLengthInBits() + 4 <= totalDataCount * 8:
            buffer.put(0, 4)

        # padding
        while buffer.getLengthInBits() % 8 != 0:
            buffer.put(False, 1)

        # padding
        while True:
            if buffer.getLengthInBits() >= totalDataCount * 8:
                break
            buffer.put(QRCode.PAD0, 8)
            if buffer.getLengthInBits() >= totalDataCount * 8:
                break
            buffer.put(QRCode.PAD1, 8)

        return QRCode._createBytes(buffer, rsBlocks)

    @staticmethod
    def _createBytes(buffer, rsBlocks):
        offset = 0

        maxDcCount = 0
        maxEcCount = 0

        dcdata = [None] * len(rsBlocks)
        ecdata = [None] * len(rsBlocks)

        for r, b in enumerate(rsBlocks):
            dcCount = b.getDataCount()
            ecCount = b.getTotalCount() - dcCount

            maxDcCount = max(maxDcCount, dcCount)
            maxEcCount = max(maxEcCount, ecCount)

            dcdata[r] = [0] * dcCount
            for i in range(len(dcdata[r])):
                dcdata[r][i] = 0xFF & buffer.getBuffer()[i + offset]
            offset += dcCount

            rsPoly = QRUtil.getErrorCorrectPolynomial(ecCount)
            rawPoly = Polynomial(dcdata[r], rsPoly.getLength() - 1)

            modPoly = rawPoly.mod(rsPoly)
            ecdata[r] = [0] * (rsPoly.getLength() - 1)
            for i in range(len(ecdata[r])):
                modIndex = i + modPoly.getLength() - len(ecdata[r])
                ecdata[r][i] = modPoly.get(modIndex) if modIndex >= 0 else 0

        totalCodeCount = sum(rsBlock.getTotalCount() for rsBlock in rsBlocks)

        data = [0] * totalCodeCount

        index = 0

        for i in range(maxDcCount):
            for r in range(len(rsBlocks)):
                if i < len(dcdata[r]):
                    data[index] = dcdata[r][i]
                    index += 1

        for i in range(maxEcCount):
            for r in range(len(rsBlocks)):
                if i < len(ecdata[r]):
                    data[index] = ecdata[r][i]
                    index += 1

        return data

    @staticmethod
    def getMinimumQRCode(data, errorCorrectLevel):
        qr = QRCode(correction=errorCorrectLevel)
        qr.addData(data)
        lv = 1
        rv = 40
        while rv - lv > 0:
            mid = (3 * lv + rv) // 4
            qr.setTypeNumber(mid)
            try:
                qr.make()
            except QRLengthError:
                if mid == 40:
                    raise inkex.AbortExtension(
                        _("The string is too large to represent as QR code")
                    )
                lv = mid + 1
            else:
                rv = mid

        qr.setTypeNumber(rv)
        qr.make()
        return qr


class Mode(object):
    MODE_NUMBER = 1 << 0
    MODE_ALPHA_NUM = 1 << 1
    MODE_8BIT_BYTE = 1 << 2
    MODE_KANJI = 1 << 3


class MaskPattern(object):
    PATTERN000 = 0
    PATTERN001 = 1
    PATTERN010 = 2
    PATTERN011 = 3
    PATTERN100 = 4
    PATTERN101 = 5
    PATTERN110 = 6
    PATTERN111 = 7


class QRUtil(object):
    @staticmethod
    def getPatternPosition(typeNumber):
        return QRUtil.PATTERN_POSITION_TABLE[typeNumber - 1]

    PATTERN_POSITION_TABLE = [
        [],
        [6, 18],
        [6, 22],
        [6, 26],
        [6, 30],
        [6, 34],
        [6, 22, 38],
        [6, 24, 42],
        [6, 26, 46],
        [6, 28, 50],
        [6, 30, 54],
        [6, 32, 58],
        [6, 34, 62],
        [6, 26, 46, 66],
        [6, 26, 48, 70],
        [6, 26, 50, 74],
        [6, 30, 54, 78],
        [6, 30, 56, 82],
        [6, 30, 58, 86],
        [6, 34, 62, 90],
        [6, 28, 50, 72, 94],
        [6, 26, 50, 74, 98],
        [6, 30, 54, 78, 102],
        [6, 28, 54, 80, 106],
        [6, 32, 58, 84, 110],
        [6, 30, 58, 86, 114],
        [6, 34, 62, 90, 118],
        [6, 26, 50, 74, 98, 122],
        [6, 30, 54, 78, 102, 126],
        [6, 26, 52, 78, 104, 130],
        [6, 30, 56, 82, 108, 134],
        [6, 34, 60, 86, 112, 138],
        [6, 30, 58, 86, 114, 142],
        [6, 34, 62, 90, 118, 146],
        [6, 30, 54, 78, 102, 126, 150],
        [6, 24, 50, 76, 102, 128, 154],
        [6, 28, 54, 80, 106, 132, 158],
        [6, 32, 58, 84, 110, 136, 162],
        [6, 26, 54, 82, 110, 138, 166],
        [6, 30, 58, 86, 114, 142, 170],
    ]

    @staticmethod
    def getErrorCorrectPolynomial(errorCorrectLength):
        a = Polynomial([1])
        for i in range(errorCorrectLength):
            a = a.multiply(Polynomial([1, QRMath.gexp(i)]))
        return a

    @staticmethod
    def getMaskFunction(maskPattern):
        return {
            MaskPattern.PATTERN000: lambda i, j: (i + j) % 2 == 0,
            MaskPattern.PATTERN001: lambda i, j: i % 2 == 0,
            MaskPattern.PATTERN010: lambda i, j: j % 3 == 0,
            MaskPattern.PATTERN011: lambda i, j: (i + j) % 3 == 0,
            MaskPattern.PATTERN100: lambda i, j: (i // 2 + j // 3) % 2 == 0,
            MaskPattern.PATTERN101: lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
            MaskPattern.PATTERN110: lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
            MaskPattern.PATTERN111: lambda i, j: ((i * j) % 3 + (i + j) % 2) % 2 == 0,
        }[maskPattern]

    @staticmethod
    def getLostPoint(qrcode: QRCode):
        moduleCount = qrcode.getModuleCount()
        lostPoint = 0

        other = qrcode.modules.astype("int")

        # LEVEL1
        same = np.zeros_like(other)
        same[:-1, :] += other[:-1, :] == other[1:, :]  # east
        same[:-1, :-1] += other[:-1, :-1] == other[1:, 1:]  # north east
        same[:, :-1] += other[:, :-1] == other[:, 1:]  # north
        same[1:, :-1] += other[1:, :-1] == other[:-1, 1:]  # north west
        same[1:, :] += other[1:, :] == other[:-1, :]  # west
        same[1:, 1:] += other[1:, 1:] == other[:-1, :-1]  # south west
        same[:, 1:] += other[:, 1:] == other[:, :-1]  # south
        same[:-1, 1:] += other[:-1, 1:] == other[1:, :-1]  # south east
        lostPoint = np.sum(np.where(same > 5, 3 + same - 5, 0))

        # LEVEL2
        lostPoint += 3 * np.sum(
            np.mod(other[:-1, :-1] + other[1:, :-1] + other[:-1, 1:] + other[1:, 1:], 4)
            == 0
        )

        # LEVEL3
        lostPoint += 40 * np.sum(
            (other[:, 0:-6] == 1)
            & (other[:, 1:-5] == 0)
            & (other[:, 2:-4] == 1)
            & (other[:, 3:-3] == 1)
            & (other[:, 4:-2] == 1)
            & (other[:, 5:-1] == 0)
            & (other[:, 6:] == 1)
        )

        lostPoint += 40 * np.sum(
            (other[0:-6] == 1)
            & (other[1:-5, :] == 0)
            & (other[2:-4, :] == 1)
            & (other[3:-3, :] == 1)
            & (other[4:-2, :] == 1)
            & (other[5:-1, :] == 0)
            & (other[6:, :] == 1)
        )

        # LEVEL4
        darkCount = np.sum(other)
        ratio = abs(100 * darkCount // moduleCount // moduleCount - 50) // 5
        lostPoint += ratio * 10

        return lostPoint

    G15 = (1 << 10) | (1 << 8) | (1 << 5) | (1 << 4) | (1 << 2) | (1 << 1) | (1 << 0)
    G18 = (
        (1 << 12)
        | (1 << 11)
        | (1 << 10)
        | (1 << 9)
        | (1 << 8)
        | (1 << 5)
        | (1 << 2)
        | (1 << 0)
    )
    G15_MASK = (1 << 14) | (1 << 12) | (1 << 10) | (1 << 4) | (1 << 1)

    @staticmethod
    def getBCHTypeInfo(data):
        d = data << 10
        while QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(QRUtil.G15) >= 0:
            d ^= QRUtil.G15 << (QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(QRUtil.G15))
        return ((data << 10) | d) ^ QRUtil.G15_MASK

    @staticmethod
    def getBCHTypeNumber(data):
        d = data << 12
        while QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(QRUtil.G18) >= 0:
            d ^= QRUtil.G18 << (QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(QRUtil.G18))
        return (data << 12) | d

    @staticmethod
    def getBCHDigit(data):
        digit = 0
        while data != 0:
            digit += 1
            data >>= 1
        return digit


class QRData(object):
    def __init__(self, mode, data):
        self._mode = mode
        self.data = data

    def getMode(self):
        return self._mode

    def getData(self):
        return self.data

    def getLength(self):
        return len(self.data)

    #    @abstractmethod
    def write(self, buffer):
        pass

    def getLengthInBits(self, type):
        if 1 <= type < 10:  # 1 - 9
            return {
                Mode.MODE_NUMBER: 10,
                Mode.MODE_ALPHA_NUM: 9,
                Mode.MODE_8BIT_BYTE: 8,
                Mode.MODE_KANJI: 8,
            }[self._mode]

        elif type < 27:  # 10 - 26
            return {
                Mode.MODE_NUMBER: 12,
                Mode.MODE_ALPHA_NUM: 11,
                Mode.MODE_8BIT_BYTE: 16,
                Mode.MODE_KANJI: 10,
            }[self._mode]

        elif type < 41:  # 27 - 40
            return {
                Mode.MODE_NUMBER: 14,
                Mode.MODE_ALPHA_NUM: 13,
                Mode.MODE_8BIT_BYTE: 16,
                Mode.MODE_KANJI: 12,
            }[self._mode]

        else:
            raise Exception("type:%s" % type)


class QR8BitByte(QRData):
    def __init__(self, data):
        super(QR8BitByte, self).__init__(Mode.MODE_8BIT_BYTE, data)
        if isinstance(data, str):
            data = data.encode("ascii", "ignore")
        if not isinstance(data, bytes):
            raise ValueError("Data must be in bytes!")

    def write(self, buffer):
        for d in self.data:
            buffer.put(ord(d), 8)


class QRAlphaNum(QRData):
    def __init__(self, data):
        super(QRAlphaNum, self).__init__(Mode.MODE_ALPHA_NUM, data)

    def write(self, buffer):
        i = 0
        while i + 1 < len(self.data):
            buffer.put(
                QRAlphaNum._getCode(self.data[i]) * 45
                + QRAlphaNum._getCode(self.data[i + 1]),
                11,
            )
            i += 2
        if i < len(self.data):
            buffer.put(QRAlphaNum._getCode(self.data[i]), 6)

    @staticmethod
    def _getCode(c):
        if "0" <= c and c <= "9":
            return ord(c) - ord("0")
        elif "A" <= c and c <= "Z":
            return ord(c) - ord("A") + 10
        else:
            dct = {
                " ": 36,
                "$": 37,
                "%": 38,
                "*": 39,
                "+": 40,
                "-": 41,
                ".": 42,
                "/": 43,
                ":": 44,
            }
            if c in dct.keys():
                return dct[c]
            else:
                raise inkex.AbortExtension(
                    _(
                        "Wrong symbol '{}' in alphanumeric representation: Should be [A-Z, 0-9] or {}"
                    ).format(c, dct.keys())
                )


class QRNumber(QRData):
    def __init__(self, data):
        super(QRNumber, self).__init__(Mode.MODE_NUMBER, data)

    def write(self, buffer):
        i = 0
        try:
            while i + 2 < len(self.data):
                num = int(self.data[i : i + 3])
                buffer.put(num, 10)
                i += 3

            if i < len(self.data):
                ln = 4 if len(self.data) - i == 1 else 7
                buffer.put(int(self.data[i:]), ln)
        except:
            raise ValueError("The string '{}' is not a valid number".format(self.data))


class QRKanji(QRData):
    def __init__(self, data):
        super(QRKanji, self).__init__(Mode.MODE_KANJI, data)
        raise RuntimeError("Class QRKanji is not implemented")


class QRMath(object):
    EXP_TABLE = None
    LOG_TABLE = None

    @staticmethod
    def _init():
        QRMath.EXP_TABLE = [0] * 256
        for i in range(256):
            QRMath.EXP_TABLE[i] = (
                1 << i
                if i < 8
                else QRMath.EXP_TABLE[i - 4]
                ^ QRMath.EXP_TABLE[i - 5]
                ^ QRMath.EXP_TABLE[i - 6]
                ^ QRMath.EXP_TABLE[i - 8]
            )

        QRMath.LOG_TABLE = [0] * 256
        for i in range(255):
            QRMath.LOG_TABLE[QRMath.EXP_TABLE[i]] = i

    @staticmethod
    def glog(n):
        return QRMath.LOG_TABLE[n]

    @staticmethod
    def gexp(n):
        return QRMath.EXP_TABLE[n % 255]


# initialize statics
QRMath._init()


class Polynomial(object):
    def __init__(self, num, shift=0):
        offset = 0
        length = len(num)
        while offset < length and num[offset] == 0:
            offset += 1
        self.num = num[offset:] + [0] * shift

    def get(self, index):
        return self.num[index]

    def getLength(self):
        return len(self.num)

    def __repr__(self):
        return ",".join([str(self.get(i)) for i in range(self.getLength())])

    def toLogString(self):
        return ",".join(
            [str(QRMath.glog(self.get(i))) for i in range(self.getLength())]
        )

    def multiply(self, e):
        num = [0] * (self.getLength() + e.getLength() - 1)
        for i in range(self.getLength()):
            for j in range(e.getLength()):
                num[i + j] ^= QRMath.gexp(
                    QRMath.glog(self.get(i)) + QRMath.glog(e.get(j))
                )
        return Polynomial(num)

    def mod(self, e):
        if self.getLength() - e.getLength() < 0:
            return self
        ratio = QRMath.glog(self.get(0)) - QRMath.glog(e.get(0))
        num = self.num[:]
        for i in range(e.getLength()):
            num[i] ^= QRMath.gexp(QRMath.glog(e.get(i)) + ratio)
        return Polynomial(num).mod(e)


class RSBlock(object):
    RS_BLOCK_TABLE = [
        # L
        # M
        # Q
        # H
        # 1
        [1, 26, 19],
        [1, 26, 16],
        [1, 26, 13],
        [1, 26, 9],
        # 2
        [1, 44, 34],
        [1, 44, 28],
        [1, 44, 22],
        [1, 44, 16],
        # 3
        [1, 70, 55],
        [1, 70, 44],
        [2, 35, 17],
        [2, 35, 13],
        # 4
        [1, 100, 80],
        [2, 50, 32],
        [2, 50, 24],
        [4, 25, 9],
        # 5
        [1, 134, 108],
        [2, 67, 43],
        [2, 33, 15, 2, 34, 16],
        [2, 33, 11, 2, 34, 12],
        # 6
        [2, 86, 68],
        [4, 43, 27],
        [4, 43, 19],
        [4, 43, 15],
        # 7
        [2, 98, 78],
        [4, 49, 31],
        [2, 32, 14, 4, 33, 15],
        [4, 39, 13, 1, 40, 14],
        # 8
        [2, 121, 97],
        [2, 60, 38, 2, 61, 39],
        [4, 40, 18, 2, 41, 19],
        [4, 40, 14, 2, 41, 15],
        # 9
        [2, 146, 116],
        [3, 58, 36, 2, 59, 37],
        [4, 36, 16, 4, 37, 17],
        [4, 36, 12, 4, 37, 13],
        # 10
        [2, 86, 68, 2, 87, 69],
        [4, 69, 43, 1, 70, 44],
        [6, 43, 19, 2, 44, 20],
        [6, 43, 15, 2, 44, 16],
        # 11
        [4, 101, 81],
        [1, 80, 50, 4, 81, 51],
        [4, 50, 22, 4, 51, 23],
        [3, 36, 12, 8, 37, 13],
        # 12
        [2, 116, 92, 2, 117, 93],
        [6, 58, 36, 2, 59, 37],
        [4, 46, 20, 6, 47, 21],
        [7, 42, 14, 4, 43, 15],
        # 13
        [4, 133, 107],
        [8, 59, 37, 1, 60, 38],
        [8, 44, 20, 4, 45, 21],
        [12, 33, 11, 4, 34, 12],
        # 14
        [3, 145, 115, 1, 146, 116],
        [4, 64, 40, 5, 65, 41],
        [11, 36, 16, 5, 37, 17],
        [11, 36, 12, 5, 37, 13],
        # 15
        [5, 109, 87, 1, 110, 88],
        [5, 65, 41, 5, 66, 42],
        [5, 54, 24, 7, 55, 25],
        [11, 36, 12, 7, 37, 13],
        # 16
        [5, 122, 98, 1, 123, 99],
        [7, 73, 45, 3, 74, 46],
        [15, 43, 19, 2, 44, 20],
        [3, 45, 15, 13, 46, 16],
        # 17
        [1, 135, 107, 5, 136, 108],
        [10, 74, 46, 1, 75, 47],
        [1, 50, 22, 15, 51, 23],
        [2, 42, 14, 17, 43, 15],
        # 18
        [5, 150, 120, 1, 151, 121],
        [9, 69, 43, 4, 70, 44],
        [17, 50, 22, 1, 51, 23],
        [2, 42, 14, 19, 43, 15],
        # 19
        [3, 141, 113, 4, 142, 114],
        [3, 70, 44, 11, 71, 45],
        [17, 47, 21, 4, 48, 22],
        [9, 39, 13, 16, 40, 14],
        # 20
        [3, 135, 107, 5, 136, 108],
        [3, 67, 41, 13, 68, 42],
        [15, 54, 24, 5, 55, 25],
        [15, 43, 15, 10, 44, 16],
        # 21
        [4, 144, 116, 4, 145, 117],
        [17, 68, 42],
        [17, 50, 22, 6, 51, 23],
        [19, 46, 16, 6, 47, 17],
        # 22
        [2, 139, 111, 7, 140, 112],
        [17, 74, 46],
        [7, 54, 24, 16, 55, 25],
        [34, 37, 13],
        # 23
        [4, 151, 121, 5, 152, 122],
        [4, 75, 47, 14, 76, 48],
        [11, 54, 24, 14, 55, 25],
        [16, 45, 15, 14, 46, 16],
        # 24
        [6, 147, 117, 4, 148, 118],
        [6, 73, 45, 14, 74, 46],
        [11, 54, 24, 16, 55, 25],
        [30, 46, 16, 2, 47, 17],
        # 25
        [8, 132, 106, 4, 133, 107],
        [8, 75, 47, 13, 76, 48],
        [7, 54, 24, 22, 55, 25],
        [22, 45, 15, 13, 46, 16],
        # 26
        [10, 142, 114, 2, 143, 115],
        [19, 74, 46, 4, 75, 47],
        [28, 50, 22, 6, 51, 23],
        [33, 46, 16, 4, 47, 17],
        # 27
        [8, 152, 122, 4, 153, 123],
        [22, 73, 45, 3, 74, 46],
        [8, 53, 23, 26, 54, 24],
        [12, 45, 15, 28, 46, 16],
        # 28
        [3, 147, 117, 10, 148, 118],
        [3, 73, 45, 23, 74, 46],
        [4, 54, 24, 31, 55, 25],
        [11, 45, 15, 31, 46, 16],
        # 29
        [7, 146, 116, 7, 147, 117],
        [21, 73, 45, 7, 74, 46],
        [1, 53, 23, 37, 54, 24],
        [19, 45, 15, 26, 46, 16],
        # 30
        [5, 145, 115, 10, 146, 116],
        [19, 75, 47, 10, 76, 48],
        [15, 54, 24, 25, 55, 25],
        [23, 45, 15, 25, 46, 16],
        # 31
        [13, 145, 115, 3, 146, 116],
        [2, 74, 46, 29, 75, 47],
        [42, 54, 24, 1, 55, 25],
        [23, 45, 15, 28, 46, 16],
        # 32
        [17, 145, 115],
        [10, 74, 46, 23, 75, 47],
        [10, 54, 24, 35, 55, 25],
        [19, 45, 15, 35, 46, 16],
        # 33
        [17, 145, 115, 1, 146, 116],
        [14, 74, 46, 21, 75, 47],
        [29, 54, 24, 19, 55, 25],
        [11, 45, 15, 46, 46, 16],
        # 34
        [13, 145, 115, 6, 146, 116],
        [14, 74, 46, 23, 75, 47],
        [44, 54, 24, 7, 55, 25],
        [59, 46, 16, 1, 47, 17],
        # 35
        [12, 151, 121, 7, 152, 122],
        [12, 75, 47, 26, 76, 48],
        [39, 54, 24, 14, 55, 25],
        [22, 45, 15, 41, 46, 16],
        # 36
        [6, 151, 121, 14, 152, 122],
        [6, 75, 47, 34, 76, 48],
        [46, 54, 24, 10, 55, 25],
        [2, 45, 15, 64, 46, 16],
        # 37
        [17, 152, 122, 4, 153, 123],
        [29, 74, 46, 14, 75, 47],
        [49, 54, 24, 10, 55, 25],
        [24, 45, 15, 46, 46, 16],
        # 38
        [4, 152, 122, 18, 153, 123],
        [13, 74, 46, 32, 75, 47],
        [48, 54, 24, 14, 55, 25],
        [42, 45, 15, 32, 46, 16],
        # 39
        [20, 147, 117, 4, 148, 118],
        [40, 75, 47, 7, 76, 48],
        [43, 54, 24, 22, 55, 25],
        [10, 45, 15, 67, 46, 16],
        # 40
        [19, 148, 118, 6, 149, 119],
        [18, 75, 47, 31, 76, 48],
        [34, 54, 24, 34, 55, 25],
        [20, 45, 15, 61, 46, 16],
    ]

    def __init__(self, totalCount, dataCount):
        self.totalCount = totalCount
        self.dataCount = dataCount

    def getDataCount(self):
        return self.dataCount

    def getTotalCount(self):
        return self.totalCount

    def __repr__(self):
        return "(total=%s,data=%s)" % (self.totalCount, self.dataCount)

    @staticmethod
    def getRSBlocks(typeNumber, errorCorrectLevel):
        rsBlock = RSBlock.getRsBlockTable(typeNumber, errorCorrectLevel)
        length = len(rsBlock) // 3
        list = []
        for i in range(length):
            count = rsBlock[i * 3 + 0]
            totalCount = rsBlock[i * 3 + 1]
            dataCount = rsBlock[i * 3 + 2]
            list += [RSBlock(totalCount, dataCount)] * count
        return list

    @staticmethod
    def getRsBlockTable(typeNumber, errorCorrectLevel):
        return {
            1: RSBlock.RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 0],
            0: RSBlock.RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 1],
            3: RSBlock.RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 2],
            2: RSBlock.RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 3],
        }[errorCorrectLevel]


class BitBuffer(object):
    def __init__(self, inclements=32):
        self.inclements = inclements
        self.buffer = [0] * self.inclements
        self.length = 0

    def getBuffer(self):
        return self.buffer

    def getLengthInBits(self):
        return self.length

    def get(self, index):
        return ((self.buffer[index // 8] >> (7 - index % 8)) & 1) == 1

    def putBit(self, bit):
        if self.length == len(self.buffer) * 8:
            self.buffer += [0] * self.inclements
        if bit:
            self.buffer[self.length // 8] |= 0x80 >> (self.length % 8)
        self.length += 1

    def put(self, num, length):
        for i in range(length):
            self.putBit(((num >> (length - i - 1)) & 1) == 1)

    def __repr__(self):
        return "".join(
            "1" if self.get(i) else "0" for i in range(self.getLengthInBits())
        )


class GridDrawer(object):
    """Mechanism to draw grids of boxes"""

    def __init__(self, invert_code, smooth_factor):
        self.invert_code = invert_code
        self.smoothFactor = smooth_factor
        self.grid = None
        self.row_count = 0
        self.col_count = 0

    def set_grid(self, grid):
        if len({len(g) for g in grid}) != 1:
            raise Exception("The array is not rectangular")
        else:
            self.grid = grid
            self.row_count = len(self.grid)
            self.col_count = len(self.grid[0])

    def isDark(self, col, row):
        inside = 0 <= col < self.col_count and 0 <= row < self.row_count
        return False if not inside else self.grid[row][col] != self.invert_code

    dm = {0: (1, 0), 1: (0, -1), 2: (-1, 0), 3: (0, 1)}

    @staticmethod
    def moveByDirection(xyd):
        return xyd[0] + GridDrawer.dm[xyd[2]][0], xyd[1] + GridDrawer.dm[xyd[2]][1]

    @staticmethod
    def makeDirectionsTable():
        result = []
        for cfg in product(range(2), repeat=4):
            result.append([])
            for d in range(4):
                if cfg[3 - d] == 0 and cfg[3 - (d - 1) % 4] != 0:
                    result[-1].append(d)
        return result

    def createVertexesForAdvDrawer(self):
        dirTable = self.makeDirectionsTable()
        result = []
        # Create vertex
        for row in range(self.row_count + 1):
            for col in range(self.col_count + 1):
                indx = (
                    (2**0 if self.isDark(col - 0, row - 1) else 0)
                    + (2**1 if self.isDark(col - 1, row - 1) else 0)
                    + (2**2 if self.isDark(col - 1, row - 0) else 0)
                    + (2**3 if self.isDark(col - 0, row - 0) else 0)
                )

                for d in dirTable[indx]:
                    result.append((col, row, d, len(dirTable[indx]) > 1))

        return result

    def getSmoothPosition(self, v, extraSmoothFactor=1.0):
        vn = self.moveByDirection(v)
        sc = extraSmoothFactor * self.smoothFactor / 2.0
        sc1 = 1.0 - sc
        return (v[0] * sc1 + vn[0] * sc, v[1] * sc1 + vn[1] * sc), (
            v[0] * sc + vn[0] * sc1,
            v[1] * sc + vn[1] * sc1,
        )


class QrCode(inkex.GenerateExtension):
    """Generate QR Code Extension"""

    def add_arguments(self, pars):
        pars.add_argument("--text", default="https://inkscape.org")
        pars.add_argument("--typenumber", type=int, default=0)
        pars.add_argument("--correctionlevel", type=int, default=0)
        pars.add_argument("--qrmode", type=int, default=0)
        pars.add_argument("--encoding", default="latin_1")
        pars.add_argument("--modulesize", type=float, default=4.0)
        pars.add_argument("--invert", type=inkex.Boolean, default="false")
        pars.add_argument(
            "--drawtype",
            default="smooth",
            choices=["smooth", "pathpreset", "selection", "symbol"],
        )
        pars.add_argument(
            "--smoothness", default="neutral", choices=["neutral", "greedy", "proud"]
        )
        pars.add_argument("--pathtype", default="simple", choices=["simple", "circle"])
        pars.add_argument("--smoothval", type=float, default=0.2)
        pars.add_argument("--symbolid", default="")
        pars.add_argument("--groupid", default="")

    def generate(self):
        scale = self.svg.unittouu("1px")  # convert to document units
        opt = self.options

        if not opt.text:
            raise inkex.AbortExtension(_("Please enter an input text"))
        elif opt.drawtype == "symbol" and opt.symbolid == "":
            raise inkex.AbortExtension(_("Please enter symbol id"))

        # for Python 3 ugly hack to represent bytes as str for Python2 compatibility
        text_str = str(opt.text)
        text_in = opt.text.replace("\\n", "\n")
        cmode = [QR8BitByte, QRNumber, QRAlphaNum, QRKanji][opt.qrmode]
        text_data = cmode(bytes(text_in, opt.encoding).decode("latin_1"))

        grp = Group()
        grp.set("inkscape:label", "QR Code: " + text_str)
        if opt.groupid:
            grp.set("id", opt.groupid)
        pos_x, pos_y = self.svg.namedview.center
        grp.transform.add_translate(pos_x, pos_y)
        if scale:
            grp.transform.add_scale(scale)

        # GENERATE THE QRCODE
        if opt.typenumber == 0:
            # Automatic QR code size`
            code = QRCode.getMinimumQRCode(text_data, opt.correctionlevel)
        else:
            # Manual QR code size
            code = QRCode(correction=opt.correctionlevel)
            code.setTypeNumber(int(opt.typenumber))
            code.addData(text_data)
            code.make()

        self.boxsize = opt.modulesize
        self.invert_code = opt.invert
        self.margin = 4
        self.draw = GridDrawer(opt.invert, opt.smoothval)
        self.draw.set_grid(code.modules)
        self.render_svg(grp, opt.drawtype)
        return grp

    def ring_iterator(self, vertices, greedy):
        visited = set()
        lut = defaultdict(list)
        for i, v in enumerate(vertices):
            lut[v[0:2]].append(i)

        def getnext(vertex):
            nextPos = self.draw.moveByDirection(vertex)
            nextIndexes = lut[nextPos[0:2]]
            if len(nextIndexes) == 0 or len(nextIndexes) > 2:
                raise Exception("Vertex " + str(next_c) + " has no connections")
            elif len(nextIndexes) == 1:
                vertsIndexNext = nextIndexes[0]
            else:
                if {vertices[nextIndexes[0]][2], vertices[nextIndexes[1]][2]} != {
                    (vertex[2] - 1) % 4,
                    (vertex[2] + 1) % 4,
                }:
                    raise Exception(
                        "Bad next vertex directions "
                        + str(vertices[nextIndexes[0]])
                        + str(vertices[nextIndexes[1]])
                    )

                # Greedy - CCW turn, proud and neutral CW turn
                vertsIndexNext = (
                    nextIndexes[0]
                    if (greedy == "g")
                    == (vertices[nextIndexes[0]][2] == (vertex[2] + 1) % 4)
                    else nextIndexes[1]
                )
            return vertices[vertsIndexNext]

        for start_vertex in reversed(vertices):
            if start_vertex in visited:
                continue

            path = [start_vertex]
            next_vertex = getnext(start_vertex)

            while start_vertex != next_vertex:
                path.append(next_vertex)
                next_vertex = getnext(next_vertex)
            else:
                yield path
                visited |= set(path)

    def render_adv(self, greedy):
        verts = self.draw.createVertexesForAdvDrawer()
        it = self.ring_iterator(verts, greedy)
        qrPath = inkex.Path()
        for ringVertices in it:
            posStart, _ = self.draw.getSmoothPosition(ringVertices[0])
            qrPath.append(Move(*self.get_svg_pos(posStart[0], posStart[1])))
            for vc, vn in circular_pairwise(ringVertices):
                if vn[2] != vc[2]:
                    if (greedy != "n") or not vn[3]:
                        # Add bezier
                        # Opt length http://spencermortensen.com/articles/bezier-circle/
                        # c = 0.552284749
                        ex = 1 - 0.552284749
                        _, bs = self.draw.getSmoothPosition(vc)
                        _, bp1 = self.draw.getSmoothPosition(vc, ex)
                        bp2, _ = self.draw.getSmoothPosition(vn, ex)
                        bf, _ = self.draw.getSmoothPosition(vn)
                        qrPath.append(Line(*self.get_svg_pos(bs[0], bs[1])))
                        qrPath.append(
                            Curve(
                                *self.get_svg_pos(bp1[0], bp1[1]),
                                *self.get_svg_pos(bp2[0], bp2[1]),
                                *self.get_svg_pos(bf[0], bf[1]),
                            )
                        )
                    else:
                        # Add straight
                        qrPath.append(Line(*self.get_svg_pos(vn[0], vn[1])))

            qrPath.append(zoneClose())

        return PathElement.new(path=qrPath)

    def render_obsolete(self):
        for row in range(self.draw.row_count):
            for col in range(self.draw.col_count):
                if self.draw.isDark(col, row):
                    x, y = self.get_svg_pos(col, row)
                    return Rectangle.new(x, y, self.boxsize, self.boxsize)

    def render_path(self, pointStr):
        singlePath = inkex.Path(self.get_icon_path_str(pointStr))
        path = inkex.Path()
        for row in range(self.draw.row_count):
            for col in range(self.draw.col_count):
                if self.draw.isDark(col, row):
                    x, y = self.get_svg_pos(col, row)
                    path.append(Move(x, y))
                    path += singlePath
                    path.append(zoneClose())
        return PathElement.new(path=path)

    def render_selection(self):
        if len(self.svg.selection) > 0:
            self.options.symbolid = self.svg.selection.first().get_id()
        else:
            raise inkex.AbortExtension(_("Please select an element to clone"))
        return self.render_symbol()

    def render_symbol(self):
        symbol = self.svg.getElementById(self.options.symbolid)
        if symbol is None:
            raise inkex.AbortExtension(
                _("Can't find symbol {}").format(self.options.symbolid)
            )
        bbox = symbol.path.bounding_box()
        transform = inkex.Transform(
            scale=(
                float(self.boxsize) / bbox.width,
                float(self.boxsize) / bbox.height,
            )
        )
        result = Group()
        for row in range(self.draw.row_count):
            for col in range(self.draw.col_count):
                if self.draw.isDark(col, row):
                    x, y = self.get_svg_pos(col, row)
                    # Inkscape doesn't support width/height on use tags
                    result.append(
                        Use.new(
                            symbol,
                            x / transform.a,
                            y / transform.d,
                            transform=transform,
                        )
                    )
        return result

    def render_pathpreset(self):
        if self.options.pathtype == "simple":
            return self.render_path("h 1 v 1 h -1")
        else:
            s = (
                "m 0.5,0.5 "
                "c 0.2761423745,0 0.5,0.2238576255 0.5,0.5 "
                "c 0,0.2761423745 -0.2238576255,0.5 -0.5,0.5 "
                "c -0.2761423745,0 -0.5,-0.2238576255 -0.5,-0.5 "
                "c 0,-0.2761423745 0.2238576255,-0.5 0.5,-0.5"
            )
            return self.render_path(s)

    render_smooth = lambda self: self.render_adv(self.options.smoothness[0])

    def render_svg(self, grp, drawtype):
        """Render to svg"""
        drawer = getattr(self, f"render_{drawtype}", self.render_obsolete)
        if drawer is None:
            raise Exception("Unknown draw type: " + drawtype)

        canvas_width = (self.draw.col_count + 2 * self.margin) * self.boxsize
        canvas_height = (self.draw.row_count + 2 * self.margin) * self.boxsize

        # white background providing margin:
        rect = grp.add(Rectangle.new(0, 0, canvas_width, canvas_height))
        rect.style["stroke"] = "none"
        rect.style["fill"] = "black" if self.invert_code else "white"

        qrg = grp.add(Group())
        qrg.style["stroke"] = "none"
        qrg.style["fill"] = "white" if self.invert_code else "black"
        qrg.add(drawer())

    def get_svg_pos(self, col, row):
        return (col + self.margin) * self.boxsize, (row + self.margin) * self.boxsize

    def get_icon_path_str(self, pointStr):
        result = ""
        digBuffer = ""
        for c in pointStr:
            if c.isdigit() or c == "-" or c == ".":
                digBuffer += c
            else:
                if len(digBuffer) > 0:
                    result += str(float(digBuffer) * self.boxsize)
                    digBuffer = ""
                result += c

        if len(digBuffer) > 0:
            result += str(float(digBuffer) * self.boxsize)

        return result


if __name__ == "__main__":
    QrCode().run()

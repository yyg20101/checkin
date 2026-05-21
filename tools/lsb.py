import time
from PIL import Image
import struct
import requests
from io import BytesIO


def embed_data(img, data):
    # 将图像转换为RGBA模式
    img = img.convert('RGBA')
    width, height = img.size
    embedded = img.copy()
    pixels = embedded.load()

    # 处理数据长度
    length = len(data)
    length_bytes = struct.pack('<I', length)
    # 生成长度位（每个字节分解为8位，高位到低位）
    length_bits = []
    for byte in length_bytes:
        for i in range(7, -1, -1):
            length_bits.append((byte >> i) & 1)

    # 生成数据位
    data_bits = []
    for byte in data:
        for i in range(7, -1, -1):
            data_bits.append((byte >> i) & 1)

    length_index = 0
    data_index = 0
    pixel_index = 1  # 从1开始计数

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            new_r, new_g, new_b = r, g, b

            # 嵌入长度信息（18-30像素）
            if 18 <= pixel_index <= 30:
                for i in range(3):  # 处理RGB三个通道
                    if length_index < len(length_bits):
                        bit = length_bits[length_index]
                        if i == 0:
                            new_r = (new_r & 0xFE) | bit
                        elif i == 1:
                            new_g = (new_g & 0xFE) | bit
                        elif i == 2:
                            new_b = (new_b & 0xFE) | bit
                        length_index += 1

            # 嵌入数据信息（从71像素开始，每隔7像素嵌入6个）
            if pixel_index >= 71:
                if pixel_index % 7 != 0:
                    for i in range(3):  # 处理RGB三个通道
                        if data_index < len(data_bits):
                            bit = data_bits[data_index]
                            if i == 0:
                                new_r = (new_r & 0xFE) | bit
                            elif i == 1:
                                new_g = (new_g & 0xFE) | bit
                            elif i == 2:
                                new_b = (new_b & 0xFE) | bit
                            data_index += 1

            # 更新像素
            pixels[x, y] = (new_r, new_g, new_b, a)
            pixel_index += 1

    return embedded


def extract_data(img):
    img = img.convert('RGBA')
    width, height = img.size
    pixels = img.load()

    length_bits = []
    data_bits = []
    pixel_index = 1

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]

            # 提取长度信息（18-30像素）
            if 18 <= pixel_index <= 30:
                length_bits.extend([r & 1, g & 1, b & 1])

            # 提取数据信息（从71像素开始，每隔7像素提取6个）
            if pixel_index >= 71:
                if pixel_index % 7 != 0:
                    data_bits.extend([r & 1, g & 1, b & 1])

            pixel_index += 1

    # 解析数据长度
    length_bits = length_bits[:32]  # 取前32位
    length_bytes = bytearray()
    for i in range(0, 32, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | length_bits[i + j]
        length_bytes.append(byte)
    length = struct.unpack('<I', length_bytes)[0]

    # 解析数据内容
    data_bits = data_bits[:length * 8]
    data = bytearray()
    for i in range(0, len(data_bits), 8):
        byte = 0
        bits = data_bits[i:i + 8]
        for bit in bits:
            byte = (byte << 1) | bit
        data.append(byte)

    return bytes(data)


# 使用示例
if __name__ == "__main__":
    # # 嵌入数据
    # original_img = Image.open("original.png").convert('RGBA')
    # secret_data = b"Hello, LSB steganography!"
    # embedded_img, _ = embed_data(original_img, secret_data)
    # embedded_img.save("embedded.png")

    # 提取数据
    url_list = ["https://the-common-images.s3.eu-central-1.amazonaws.com/common_dev.png",
                "https://the-common-images.s3.eu-central-1.amazonaws.com/common_fat.png",
                "https://the-common-images.s3.eu-central-1.amazonaws.com/common_pre.png",
                "https://the-common-images.s3.eu-central-1.amazonaws.com/common_pro.png"]
    for url in url_list:
        response = requests.get(url)
        if response.status_code == 200:
            embedded_img = Image.open(BytesIO(response.content))
            start_time = time.time()
            extracted_data = extract_data(embedded_img)
            end_time = time.time()
            print("Url:", url)
            print("Extracted data:", extracted_data.decode())
            print("图片解析耗时:", end_time - start_time)
            print("*" * 200)

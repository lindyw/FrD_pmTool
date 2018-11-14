# import cv2
# # import MovieUtils
# # import hachoir - metadata
# # import numpy
# # print cv2.__version__
# success = True
# count = 0
# path = 'C:/Users/Lindy/Desktop/_origMov/cw2_sc16d_sh002_com_v02\cw2_sc16d_sh002_com_v02.mov'
# video = cv2.VideoCapture(path)
# frames = video.get(5)
# # frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
# print frames
import imageio
path = 'C:/Users/Lindy/Desktop/_origMov/cw2_sc16d_sh002_com_v02\cw2_sc16d_sh002_com_v02.mov'
vid = imageio.get_reader(path, 'ffmpeg')
num_frames = vid._meta['nframes']
print num_frames

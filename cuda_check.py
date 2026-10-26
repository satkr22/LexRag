import torch
import onnxruntime as ort
print("Provider:", ort.get_available_providers())
print("CUDA Version:", torch.version.cuda)
print("cuDNN Version:", torch.backends.cudnn.version())

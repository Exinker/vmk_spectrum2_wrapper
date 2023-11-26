import time

from libspectrum2_wrapper.device import Device, DeviceEthernetConfig
from libspectrum2_wrapper.storage import BufferDeviceStorage


# setup device
device =  Device(
    storage=BufferDeviceStorage(
        buffer_size=1,
        buffer_handler=None,
    ),
    verbose=True,
)
device = device.create(
    config=DeviceEthernetConfig(
        ip='10.116.220.2',
    ),
)
device = device.connect()
device = device.set_exposure(2)


# начать измерения (блокирующие)
value = device.await_read(1000)

print(len(device.storage.data), len(device.storage.buffer))
print(value.shape)


# начать измерения в буфер (не блокирующие)
value = device.read(1000)

print(len(device.storage.data), len(device.storage.buffer))
time.sleep(2)

import sys
import time
import threading
from dataclasses import dataclass
from typing import Callable, TypeAlias

import numpy as np

from pyspectrum2 import DeviceManager, DeviceStatusCode, DeviceStatus

from .alias import Array, Second, MilliSecond, MicroSecond
from .storage import DeviceStorage


sys.path.append('cmake-build-debug/binding')


# --------        device config        --------
@dataclass
class DeviceEthernetConfig:
    ip: str

    change_exposure_delay: MilliSecond = 1000


DeviceConfig: TypeAlias = DeviceEthernetConfig


# --------        device        --------
class Device:

    def __init__(self, config: DeviceConfig, storage: DeviceStorage | None, verbose: bool = False) -> None:

        self.condition = threading.Condition()

        # device
        self._config = config
        self._device = None
        self._status = None
        self._storage = storage
        self._exposure = None

        self._change_exposure_delay = config.change_exposure_delay
        self._verbose = verbose

    def connect(self, timeout: Second = 5) -> 'Device':
        """Connect to device."""

        time_start = time.perf_counter()

        try:
            self._device = create_device(
                config=self._config,
                on_frame=self._on_frame,
                on_status=self._on_status,
            )
            self._device.run()

            with self.condition:
                while not self.is_status_connected:
                    if time.perf_counter() - time_start > timeout:
                        raise ConnectionError('Connection timeout error')  # TODO: add custom exception!

                    self.condition.wait(.01)

        except ConnectionError as error:
            print(error)

        finally:
            if self._verbose:
                print('Status code: {code}.'.format(code=self.status_code))

            return self

    # --------        exposure        --------
    @property
    def exposure(self) -> MilliSecond | None:
        return self._exposure

    def set_exposure(self, exposure: MilliSecond) -> 'Device':
        """Set exposure."""
        assert self._device is not None, 'Connect and setup a device before'
        assert self.is_status_connected, 'Device is not connected!'

        if exposure == self._exposure:
            return self

        # setup exposure
        try:
            self._device.set_exposure(self._to_microsecond(exposure))

        except AssertionError as error:
            print(error)

        else:
            self._exposure = exposure
            time.sleep(self._to_second(self._change_exposure_delay)) # delay to setup exposure

        finally:
            if self._verbose:
                print('Exposure: {exposure} ms.'.format(exposure=self.exposure))

            return self

    @staticmethod
    def _to_microsecond(__exposure: MilliSecond) -> MicroSecond:
        value = int(np.round(1000 * __exposure).astype(int))

        assert value % 100 == 0, 'Invalid exposure: {value} mks!'.format(
            value=value,
        )

        return value

    @staticmethod
    def _to_second(__exposure: MilliSecond) -> Second:
        return __exposure / 1000

    # --------        storage        --------
    @property
    def storage(self) -> DeviceStorage | None:
        return self._storage

    def set_storage(self, storage: DeviceStorage) -> 'Device':
        """"""
        assert isinstance(storage, DeviceStorage)
        self._storage = storage
        
        return self

    # --------        status        --------
    @property
    def status(self) -> DeviceStatus | None:
        return self._status

    @property
    def status_code(self) -> DeviceStatusCode | None:
        if self.status is None:
            return None
        return self.status.code

    @property
    def is_status_connected(self) -> bool:
        if self.status is None:
            return False

        return self.status_code in (
            DeviceStatusCode.CONNECTED,
            DeviceStatusCode.DONE_READING,  # после переподключения устройсто может находиться с состояние `DONE_READING`
        )

    @property
    def is_status_reading(self) -> bool:
        if self.status is None:
            return False

        return self.status_code in (
            DeviceStatusCode.READING,
        )

    @property
    def is_status_read(self) -> bool:
        if self.status is None:
            return False

        return self.status_code in (
            DeviceStatusCode.DONE_READING,
        )

    # --------        handlers        --------
    def await_read(self, n_frames: int | None = None) -> Array[int]:
        """Прочитать `n_frames` кадров и вернуть их (blocking)."""
        assert self._device is not None, 'Connect and setup a device before'
        assert self.storage is not None, 'Setup a storage before!'
        assert self.exposure is not None, 'Setup an exposure before!'
        assert self.is_status_connected, 'Device is not ready to read! Device status is {code}'.format(
            code=self.status_code,
        )

        if n_frames is None:
            n_frames = self.storage.buffer_size

        # read
        self._device.read(n_frames)

        with self.condition:
            while not self.is_status_reading:
                self.condition.wait(.01)
            while not self.is_status_read:
                self.condition.wait(.01)

        try:
            return np.array(self.storage.data)
        finally:
            self.storage.data.clear()

    def read(self, n_frames: int | None = None) -> None:
        """Прочитать `n_frames` кадров в `storage` (non blocking)."""
        assert self._device is not None, 'Connect and setup a device before'
        assert self.storage is not None, 'Setup a storage before!'
        assert self.exposure is not None, 'Setup an exposure before!'
        assert self.is_status_connected, 'Device is not ready to read! Device status is {code}'.format(
            code=self.status_code,
        )

        if n_frames is None:
            n_frames = self.storage.buffer_size

        # read
        self._device.read(n_frames)

    # --------        callbacks        --------
    def _on_frame(self, frame: Array[int]) -> None:
        self.storage.put(frame)

    def _on_status(self, status: DeviceStatus) -> None:
        self._status = status

        # notify all
        with self.condition:
            self.condition.notify_all()

        # exception
        if status.code == DeviceStatusCode.ERROR:
            timeout = self.storage._finished_at - self.storage._started_at
            content = '\n'.join([
                'description: {description}'.format(
                    description=status.description,
                ),
                'buffer: {size:0>4s}'.format(
                    size=len(self.storage._buffer),
                ),
                'data: {str(size):0>4s}'.format(
                    size=len(self.storage.data),
                ),
                'running for {hours}:{minutes}:{seconds}'.format(
                    hours=f'{str(int((timeout) // 3600)):0>2s}',
                    minutes=f'{str(int((timeout) // 60)):0>2s}',
                    seconds=f'{str(int((timeout) % 60)):0>2s}',
                ),
            ])

            raise ConnectionError(content)  # TODO: add custom exception!

    # --------        callbacks        --------
    def __repr__(self) -> str:
        cls = self.__class__

        return '{name}({content})'.format(
            name=cls.__name__,
            content=', '.join([
                'status code: {code}'.format(
                    code=self.status_code,
                ),
                'exposure: {exposure}{units}'.format(
                    exposure='None' if self.exposure is None else f'{self.exposure}',
                    units='' if self.exposure is None else f'ms',
                ),
            ])
        )


def create_device(config: DeviceConfig, on_frame: Callable, on_status: Callable | None) -> Device:

    if isinstance(config, DeviceEthernetConfig):
        device = DeviceManager(config.ip)
        device.set_frame_callback(on_frame)
        device.set_status_callback(on_status)

        return device

    raise ValueError(f'Device {type(config).__name__} is not supported yet!')

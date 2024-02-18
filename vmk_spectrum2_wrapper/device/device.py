import sys
import time
import threading
from typing import Callable

import numpy as np

from pyspectrum2 import DeviceManager, DeviceStatusCode, DeviceStatus

from vmk_spectrum2_wrapper.storage import DeviceStorage
from vmk_spectrum2_wrapper.typing import Array, MicroSecond, MilliSecond, Second

from .config import DeviceConfig, DeviceEthernetConfig
from .exceptions import CreateDeviceError, ConnectionDeviceError, StatusDeviceError, SetupDeviceError


sys.path.append('cmake-build-debug/binding')


class Device:

    def __init__(self, storage: DeviceStorage, verbose: bool = False) -> None:

        self.condition = threading.Condition()

        # device
        self._device = None
        self._status = None
        self._exposure = None
        self._storage = storage

        self._verbose = verbose

    def create(self, config: DeviceConfig) -> 'Device':
        """Create a device."""

        def _create_device(config: DeviceConfig, on_frame: Callable, on_status: Callable | None) -> Device:
            """Create device by config and callbacks."""

            if isinstance(config, DeviceEthernetConfig):
                device = DeviceManager(config.ip)
                device.set_frame_callback(on_frame)
                device.set_status_callback(on_status)

                return device

            raise ValueError(f'Device {type(config).__name__} is not supported yet!')

        self._device = _create_device(
            config=config,
            on_frame=self._on_frame,
            on_status=self._on_status,
        )
        self._status = None
        self._exposure = None

        self._change_exposure_delay = config.change_exposure_delay

        return self

    def connect(self, timeout: Second = 5) -> 'Device':
        """Connect to device."""

        # checkup to connect
        if self._device is None:
            raise CreateDeviceError('Create a device before!')

        if self.is_status(codes=(DeviceStatusCode.DISCONNECTED, )):
            raise ConnectionDeviceError('Create a new device to reconnection!')

        # connect
        time_start = time.perf_counter()
        try:
            self._device.run()

            with self.condition:
                while not self.is_status(codes=(DeviceStatusCode.CONNECTED, DeviceStatusCode.DONE_READING, )):
                    if time.perf_counter() - time_start > timeout:
                        raise ConnectionDeviceError('Connection timeout error!')

                    self.condition.wait(.01)

        except ConnectionDeviceError as error:
            print(error)

        #
        return self

    def disconnect(self, timeout: Second = 5) -> 'Device':
        """Disconnect from device."""

        # checkup to disconnect
        if self._device is None:
            raise CreateDeviceError('Create a device before!')

        # disconnect
        time_start = time.perf_counter()
        try:
            self._device.stop()

            with self.condition:
                while not self.is_status(codes=(DeviceStatusCode.DISCONNECTED, )):
                    if time.perf_counter() - time_start > timeout:
                        raise ConnectionDeviceError('Disconnection timeout error!')

                    self.condition.wait(.01)

        except ConnectionDeviceError as error:
            print(error)

        #
        return self

    # --------        exposure        --------
    @property
    def exposure(self) -> MilliSecond | None:
        return self._exposure

    def set_exposure(self, exposure: MilliSecond) -> 'Device':
        """Set exposure."""
        if exposure == self._exposure:
            return self

        # checkup
        self._checkup_to_set_exposure()

        # set
        try:
            self._device.set_exposure(self._to_microsecond(exposure))
        except AssertionError as error:
            print(error)
        else:
            self._exposure = exposure
            time.sleep(self._to_second(self._change_exposure_delay))  # delay after exposure update

        #
        if self._verbose:
            print('Set exposure: {exposure} ms.'.format(exposure=self.exposure))

        return self

    def _checkup_to_set_exposure(self) -> bool:
        """Checkup device to set exposure."""

        # check components
        if self._device is None:
            raise CreateDeviceError('Create a device before!')

        # check status
        if not self.is_status(codes=(DeviceStatusCode.CONNECTED, DeviceStatusCode.DONE_READING)):
            message = 'Device is not ready to set exposure! Device status is `{code}`. Connect to device before!'.format(
                code=self.status_code,
            )
            raise StatusDeviceError(message)

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

    def is_status(self, codes: tuple[DeviceStatusCode]) -> bool:
        if self.status is None:
            return False

        return self.status_code in codes

    # --------        read        --------
    def await_read(self, n_frames: int | None = None) -> Array[int]:
        """Прочитать `n_frames` кадров и вернуть их (blocking)."""

        # checkup
        self._checkup_to_read()

        # read
        self._device.read(
            self.storage.buffer_size if n_frames is None else n_frames
        )

        with self.condition:
            while not self.is_status(codes=(DeviceStatusCode.READING,)):
                self.condition.wait(.01)
            while not self.is_status(codes=(DeviceStatusCode.DONE_READING,)):
                self.condition.wait(.01)

        return self.storage.pull()

    def read(self, n_frames: int | None = None) -> None:
        """Прочитать `n_frames` кадров в `storage` (non blocking)."""

        # checkup
        self._checkup_to_read()

        # read
        self._device.read(
            self.storage.buffer_size if n_frames is None else n_frames
        )

    def _checkup_to_read(self) -> bool:
        """Checkup device to read data."""

        # check components
        if self._device is None:
            raise CreateDeviceError('Create a device before!')

        if self.storage is None:
            raise SetupDeviceError('Setup a storage before!')

        if self.exposure is None:
            raise SetupDeviceError('Setup a exposure before!')

        # check status
        if not self.is_status(codes=(DeviceStatusCode.CONNECTED, DeviceStatusCode.DONE_READING)):
            message = 'Device is not ready to read! Device status is `{code}`.'.format(
                code=self.status_code,
            )
            raise StatusDeviceError(message)

        # clear storage
        self.storage.clear()

    # --------        callbacks        --------
    def _on_frame(self, frame: Array[int]) -> None:
        self.storage.put(frame)

    def _on_status(self, status: DeviceStatus) -> None:
        self._status = status

        # notify all
        with self.condition:
            self.condition.notify_all()

        # verbose
        if self._verbose:
            print('Status code: `{code}`.'.format(code=self.status_code))

    # --------        private        --------
    def __repr__(self) -> str:
        cls = self.__class__

        return '{name}({content})'.format(
            name=cls.__name__,
            content=', '.join([
                'status code: `{code}`'.format(
                    code=self.status_code,
                ),
                'exposure: {exposure}{units}'.format(
                    exposure='None' if self.exposure is None else f'{self.exposure}',
                    units='' if self.exposure is None else 'ms',
                ),
            ])
        )

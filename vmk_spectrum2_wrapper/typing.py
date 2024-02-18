from typing import TypeAlias, NewType

from numpy.typing import NDArray


# --------        types        --------
Array: TypeAlias = NDArray


# --------        time units        --------
Second = NewType('Second', float)
MilliSecond = NewType('MilliSecond', float)
MicroSecond = NewType('MicroSecond', int)

Hz = NewType('Hz', float)


# --------        spacial units        --------
Meter = NewType('Meter', float)
NanoMeter = NewType('NanoMeter', float)

Number = NewType('Number', float)


# --------        value units        --------
Absorbance = NewType('Absorbance', float)
Electron = NewType('Electron', float)
Percent = NewType('Percent', float)

from enum import Enum


class Units(Enum):
    """Device's output signal units."""
    digit = 'digit'
    percent = 'percent'
    electron = 'electron'


def get_units(__kind: str) -> Units:
    """Get unit's of output signal."""

    match __kind:
        case 'digit':
            return Units.digit
        case 'percent':
            return Units.percent
        case 'electron':
            raise NotImplementedError

    raise NotImplementedError


def get_units_clipping(units: Units) -> float:
    """Get unit's clipping value (max value)."""

    match units:
        case Units.digit:
            adc = 16
            return 2**adc - 1
        case Units.percent:
            return 100
        case Units.electron:
            raise NotImplementedError


def get_units_scale(units: Units) -> float:
    """Get unit's scale coefficient."""

    return get_units_clipping(units) / get_units_clipping(Units.digit)


def get_units_label(units: Units) -> str:
    """Get units's label."""

    match units:
        case Units.digit:
            return r''
        case Units.percent:
            return r'[%]'
        case Units.electron:
            return r'[$e^{-}$]'

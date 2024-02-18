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

    raise TypeError(f'Units {__kind} is not supported yet!')


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

    raise TypeError(f'Units {units} is not supported yet!')


def get_units_scale(units: Units) -> float:
    """Get unit's scale coefficient."""

    return get_units_clipping(units) / get_units_clipping(Units.digit)


def get_units_label(units: Units, is_enclosed: bool = True) -> str:
    """Get units's label."""

    match units:
        case Units.digit:
            label = r''
        case Units.percent:
            label = r'%'
        case Units.electron:
            label = r'$e^{-}$'
        case _:
            raise TypeError(f'Units {units} is not supported yet!')

    #
    if is_enclosed:
        return f'[{label}]'

    return label


def to_electron(value: float, units: Units, capacity: float) -> float:
    """Convert value to electron units."""

    match units:
        case Units.digit:
            adc = 16
            return capacity * (value/(2**adc - 1))
        case Units.percent:
            return capacity * (value/100)
        case Units.electron:
            return value

    raise TypeError(f'Units {units} is not supported yet!')

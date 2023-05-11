class HexBinary8(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 2:
            raise ValueError("HexBinary8 max length of 2.")
        return cls(v)


class HexBinary16(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 4:
            raise ValueError("HexBinary16 max length of 4.")
        return cls(v)


class HexBinary32(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 8:
            raise ValueError("HexBinary32 max length of 8.")
        return cls(v)


class HexBinary48(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 12:
            raise ValueError("HexBinary48 max length of 12.")
        return cls(v)


class HexBinary64(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 16:
            raise ValueError("HexBinary64 max length of 16.")
        return cls(v)


class HexBinary128(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 32:
            raise ValueError("HexBinary128 max length of 32.")
        return cls(v)


class HexBinary160(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 40:
            raise ValueError("HexBinary160 max length of 40.")
        return cls(v)

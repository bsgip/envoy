class HexBinary32(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 8:
            raise ValueError("HexBinary32 max length of 8.")
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

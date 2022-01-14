import pytest
from slipcover import slipcover as sc
import dis
import sys
import struct


PYTHON_VERSION = sys.version_info[0:2]


def current_line():
    import inspect as i
    return i.getframeinfo(i.currentframe().f_back).lineno

def current_file():
    import inspect as i
    return i.getframeinfo(i.currentframe().f_back).filename

def from_set(s: set):
    return next(iter(s))

@pytest.fixture(autouse=True)
def clear_slipcover():
    sc.clear()

def test_opcode_arg():
    JUMP = sc.op_JUMP_ABSOLUTE
    EXT = sc.op_EXTENDED_ARG

    assert [JUMP, 0x42] == list(sc.opcode_arg(JUMP, 0x42))
    assert [EXT, 0xBA, JUMP, 0xBE] == list(sc.opcode_arg(JUMP, 0xBABE))
    assert [EXT, 0xBA, EXT, 0xBE, JUMP, 0xFA] == \
           list(sc.opcode_arg(JUMP, 0xBABEFA))
    assert [EXT, 0xBA, EXT, 0xBE, EXT, 0xFA, JUMP, 0xCE] == \
           list(sc.opcode_arg(JUMP, 0xBABEFACE))

    assert [EXT, 0, JUMP, 0x42] == list(sc.opcode_arg(JUMP, 0x42, min_ext=1))
    assert [EXT, 0, EXT, 0, JUMP, 0x42] == list(sc.opcode_arg(JUMP, 0x42, min_ext=2))
    assert [EXT, 0, EXT, 0, EXT, 0, JUMP, 0x42] == \
           list(sc.opcode_arg(JUMP, 0x42, min_ext=3))

def test_get_jumps():
    def foo(x):
        for _ in range(2):      # FOR_ITER is relative
            if x: print(True)
            else: print(False)

    code = foo.__code__.co_code
    jumps = sc.get_jumps(code)
    dis.dis(foo)
    assert 4 == len(jumps)  # may be brittle

    for i, j in enumerate(jumps):
        assert 2 == j.length
        assert code[j.offset+j.length-2] == j.opcode
        assert (j.opcode in dis.hasjabs) or (j.opcode in dis.hasjrel)
        assert (j.opcode in dis.hasjrel) == j.is_relative
        if i > 0: assert jumps[i-1].offset < j.offset

    # the tests below are more brittle... they rely on a 'for' loop
    # being created with
    #
    #   loop: FOR_ITER done
    #            ...
    #         JUMP_ABSOLUTE loop
    #   done: ...

    assert dis.opmap["FOR_ITER"] == jumps[0].opcode
    assert dis.opmap["JUMP_ABSOLUTE"] == jumps[-1].opcode

    assert jumps[0].is_relative
    assert not jumps[-1].is_relative

    assert jumps[0].target == jumps[-1].offset+2    # to finish loop
    assert jumps[-1].target == jumps[0].offset      # to continue loop


# Test case building rationale:
#
# There are relative and absolute jumps; both kinds have an offset (where
# the operation is located) and a target (absolute offset for the jump,
# resolved from the argument).
# 
# On forward jumps, an insertion can happen before the offset, at the offset,
# between the offset and the target, at the target, or after the target.
# On backward jumps, an insertion can happen before the target, between the
# target and the offset, at the offset, or after the offset.
#
# Jumps have an offset (op address) and a target (absolute jump address).
# There are relative and absolute jumps; absolute jumps may jump forward
# or backward.  In absolute forward jumps, the offset (op address) precedes
# the target and in backwards

def test_jump_adjust_abs_fw_before_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(108))
    j.adjust(90, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 110 == j.target
    assert sc.offset2jump(108) != j.arg()

def test_jump_adjust_abs_fw_at_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(108))
    j.adjust(100, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 110 == j.target
    assert sc.offset2jump(108) != j.arg()

def test_jump_adjust_abs_fw_after_offset_before_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(108))
    j.adjust(105, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 110 == j.target
    assert sc.offset2jump(108) != j.arg()

def test_jump_adjust_abs_fw_at_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(108))
    j.adjust(108, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 108 == j.target
    assert sc.offset2jump(108) == j.arg()

def test_jump_adjust_abs_fw_after_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(108))
    j.adjust(110, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 108 == j.target
    assert sc.offset2jump(108) == j.arg()

def test_jump_adjust_abs_bw_before_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(90))
    j.adjust(50, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 92 == j.target
    assert sc.offset2jump(90) != j.arg()

def test_jump_adjust_abs_bw_at_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(90))
    j.adjust(90, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 90 == j.target
    assert sc.offset2jump(90) == j.arg()

def test_jump_adjust_abs_bw_after_target_before_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(90))
    j.adjust(96, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 90 == j.target
    assert sc.offset2jump(90) == j.arg()

def test_jump_adjust_abs_bw_at_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(90))
    j.adjust(100, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 90 == j.target
    assert sc.offset2jump(90) == j.arg()

def test_jump_adjust_abs_bw_after_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjabs), arg=sc.offset2jump(90))
    j.adjust(110, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 90 == j.target
    assert sc.offset2jump(90) == j.arg()

def test_jump_adjust_rel_fw_before_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(90, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 134 == j.target
    assert sc.offset2jump(30) == j.arg()

def test_jump_adjust_rel_fw_at_offset():
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(100, 2)

    assert 102 == j.offset
    assert 2 == j.length
    assert 134 == j.target
    assert sc.offset2jump(30) == j.arg()

def test_jump_adjust_rel_fw_after_offset_before_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(105, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 134 == j.target
    assert sc.offset2jump(30) != j.arg()

def test_jump_adjust_rel_fw_at_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(132, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 132 == j.target
    assert sc.offset2jump(30) == j.arg()

def test_jump_adjust_rel_fw_after_target():
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(140, 2)

    assert 100 == j.offset
    assert 2 == j.length
    assert 132 == j.target
    assert sc.offset2jump(30) == j.arg()


def test_jump_adjust_length_no_change():
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(10, 50)

    change = j.adjust_length()
    assert 0 == change
    assert 2 == j.length


@pytest.mark.parametrize("N, increase_by", [(0x100, 2), (0x10000, 4)])
def test_jump_adjust_length_increases(N, increase_by):
    j = sc.JumpOp(100, 2, from_set(dis.hasjrel), arg=sc.offset2jump(30))
    j.adjust(102, sc.jump2offset(N))

    change = j.adjust_length()
    assert increase_by == change
    assert 2+change == j.length


def test_jump_adjust_length_decreases():
    j = sc.JumpOp(100, 4, from_set(dis.hasjrel), arg=sc.offset2jump(30))

    change = j.adjust_length()
    assert 0 == change
    assert 4 == j.length


def unpack_lnotab(lnotab: bytes) -> list:
    return list(struct.unpack("Bb" * (len(lnotab)//2), lnotab))


def test_make_lnotab():
    lines = [sc.LineEntry(0, 6, 1),
             sc.LineEntry(6, 50, 2),
             sc.LineEntry(50, 350, 7),
             sc.LineEntry(350, 361, 207),
             sc.LineEntry(361, 370, 208),
             sc.LineEntry(370, 380, 50)]

    lnotab = sc.make_lnotab(0, lines)

    assert [0, 1,
            6, 1,
            44, 5,
            255, 0,
            45, 127,
            0, 73,
            11, 1,
            9, -128,
            0, -30] == unpack_lnotab(lnotab)


def test_make_linetable():
    lines = [sc.LineEntry(0, 6, 1),
             sc.LineEntry(6, 50, 2),
             sc.LineEntry(50, 350, 7),
             sc.LineEntry(350, 360, None),
             sc.LineEntry(360, 376, 8),
             sc.LineEntry(376, 380, 208),
             sc.LineEntry(380, 390, 50)]    # XXX this is presumptive, check for accuracy

    linetable = sc.make_linetable(0, lines)

    assert [6, 1,
            44, 1,
            254, 5,
            46, 0,
            10, -128,
            16, 1,
            0, 127,
            4, 73,
            0, -127,
            10, -31] == unpack_lnotab(linetable)


def lines_from_code(code):
    if PYTHON_VERSION >= (3,10):
        return [sc.LineEntry(*l) for l in code.co_lines()]

    lines = [sc.LineEntry(start, 0, number) \
            for start, number in dis.findlinestarts(code)]
    for i in range(len(lines)-1):
        lines[i].end = lines[i+1].start
    lines[-1].end = len(code.co_code)
    return lines


def test_make_lines_and_compare():
    # XXX test with more code!
    def foo(n):
        x = 0

        for i in range(n):
            x += (i+1)

        return x

    if PYTHON_VERSION >= (3,10):
        my_linetable = sc.make_linetable(foo.__code__.co_firstlineno,
                                         lines_from_code(foo.__code__))
        assert list(foo.__code__.co_linetable) == list(my_linetable)


    my_lnotab = sc.make_lnotab(foo.__code__.co_firstlineno,
                               lines_from_code(foo.__code__))
    assert list(foo.__code__.co_lnotab) == list(my_lnotab)


def test_instrument():
    first_line = current_line()+2
    def foo(n):
        x = 0
        for i in range(n):
            x += (i+1)
        return x
    last_line = current_line()

    sc.instrument(foo)

    # Are all lines where we expect?
    for (offset, _) in dis.findlinestarts(foo.__code__):
        assert sc.op_NOP == foo.__code__.co_code[offset]

    dis.dis(foo)
    assert 6 == foo(3)

    assert {current_file(): {*range(first_line, last_line)}} == sc.get_coverage()


@pytest.mark.parametrize("N", [2, 20, 128, 256, 512, 4096, 8192, 65536, 131072])
def test_instrument_long_jump(N):
    # each 'if' adds a jump
    first_line = current_line()+2
    src = "x = 0\n" + \
          "while x == 0:\n" + \
          "  if x >= 0:\n" + \
          "    x += 1\n" * N

    code = compile(src, "foo", "exec")

    assert 2 <= len(sc.get_jumps(code.co_code))

    code = sc.instrument(code)

    # Are all lines where we expect?
    for (offset, _) in dis.findlinestarts(code):
        # This catches any lines not where we expect,
        # such as any not adjusted after adjusting jump lengths
        assert sc.op_NOP == code.co_code[offset]

    exec(code, locals(), globals())
    assert N == x
    assert {"foo": {*range(1, 1+N+3)}} == sc.get_coverage()


def test_deinstrument():
    first_line = current_line()+2
    def foo(n):
        x = 0
        for i in range(n):
            x += (i+1)
        return x
    last_line = current_line()

    assert not sc.get_coverage()

    sc.instrument(foo)
    sc.deinstrument(foo, {*range(first_line, last_line)})
    assert 6 == foo(3)
    assert not sc.get_coverage()


def test_deinstrument_some():
    first_line = current_line()+2
    def foo(n):
        x = 0
        for i in range(n):
            x += (i+1)
        return x
    last_line = current_line()

    assert not sc.get_coverage()

    sc.instrument(foo)
    sc.deinstrument(foo, {first_line, last_line-1})

    assert 6 == foo(3)
    assert {current_file(): {*range(first_line+1, last_line-1)}} == sc.get_coverage()

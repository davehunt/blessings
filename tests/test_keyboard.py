# -*- coding: utf-8 -*-
"""Tests for keyboard support."""
import curses
import time
import math
import pty
import sys
import os

from accessories import (
    read_until_eof,
    read_until_semaphore,
    SEND_SEMAPHORE,
    as_subprocess,
    TestTerminal,
    SEMAPHORE,
    all_terms,
    echo_off,
    xterms,
)

import mock


def test_inkey_0s_noinput():
    """0-second inkey without input; '' should be returned."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 0.0)
    child()


def test_inkey_1s_noinput():
    """1-second inkey without input; '' should be returned after ~1 second."""
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=1)
            assert (inp == u'')
            assert (math.floor(time.time() - stime) == 1.0)
    child()


def test_inkey_0s_input():
    """0-second inkey with input; Keypress should be immediately returned."""
    pid, master_fd = pty.fork()
    if pid is 0:
        # child pauses, writes semaphore and begins awaiting input
        term = TestTerminal()
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), inp)
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, u'x'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert (output == u'x')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 0.0)


def test_inkey_0s_multibyte_utf8():
    """0-second inkey with multibyte utf-8 input; should decode immediately."""
    # utf-8 bytes represent "latin capital letter upsilon".
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, SEND_SEMAPHORE)
        os.write(master_fd, u'\u01b1'.encode('utf-8'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert (output == u'Ʊ')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 0.0)


def test_inkey_0s_sequence():
    """0-second inkey with multibyte sequence; should decode immediately."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), ('%s' % (inp.name,)))
            sys.stdout.flush()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, u'\x1b[D'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        output = read_until_eof(master_fd)
    pid, status = os.waitpid(pid, 0)
    assert (output == u'KEY_LEFT')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 0.0)


def test_inkey_1s_input():
    """1-second inkey w/multibyte sequence; should return after ~1 second."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            inp = term.inkey(timeout=3)
            os.write(sys.__stdout__.fileno(), ('%s' % (inp.name,)))
            sys.stdout.flush()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        time.sleep(1)
        os.write(master_fd, u'\x1b[C'.encode('ascii'))
        output = read_until_eof(master_fd)

    pid, status = os.waitpid(pid, 0)
    assert (output == u'KEY_RIGHT')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 1.0)


def test_esc_delay_035():
    """esc_delay will cause a single ESC (\\x1b) to delay for 0.35."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=5)
            os.write(sys.__stdout__.fileno(), ('%s %i' % (
                inp.name, (time.time() - stime) * 100,)))
            sys.stdout.flush()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, u'\x1b'.encode('ascii'))
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert (key_name == u'KEY_ESCAPE')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 0.0)
    assert 35 <= int(duration_ms) <= 45, duration_ms


def test_esc_delay_135():
    """esc_delay=1.35 will cause a single ESC (\\x1b) to delay for 1.35."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=5, esc_delay=1.35)
            os.write(sys.__stdout__.fileno(), ('%s %i' % (
                inp.name, (time.time() - stime) * 100,)))
            sys.stdout.flush()
        os._exit(0)

    with echo_off(master_fd):
        read_until_semaphore(master_fd)
        stime = time.time()
        os.write(master_fd, u'\x1b'.encode('ascii'))
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert (key_name == u'KEY_ESCAPE')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 1.0)
    assert 135 <= int(duration_ms) <= 145, int(duration_ms)


def test_esc_delay_timout_0():
    """esc_delay still in effect with timeout of 0 ("nonblocking")."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        os.write(sys.__stdout__.fileno(), SEMAPHORE)
        with term.cbreak():
            stime = time.time()
            inp = term.inkey(timeout=0)
            os.write(sys.__stdout__.fileno(), ('%s %i' % (
                inp.name, (time.time() - stime) * 100,)))
            sys.stdout.flush()
        os._exit(0)

    with echo_off(master_fd):
        os.write(master_fd, u'\x1b'.encode('ascii'))
        read_until_semaphore(master_fd)
        stime = time.time()
        key_name, duration_ms = read_until_eof(master_fd).split()

    pid, status = os.waitpid(pid, 0)
    assert (key_name == u'KEY_ESCAPE')
    assert (os.WEXITSTATUS(status) == 0)
    assert (math.floor(time.time() - stime) == 0.0)
    assert 35 <= int(duration_ms) <= 45, int(duration_ms)


def test_no_keystroke():
    """Test keyboard.Keystroke constructor with default arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke()
    assert ks._name is None
    assert ks.name == ks._name
    assert ks._code is None
    assert ks.code == ks._code
    assert u'x' == u'x' + ks
    assert ks.is_sequence is False
    assert repr(ks) == "u''"


def test_a_keystroke():
    """Test keyboard.Keystroke constructor with set arguments."""
    from blessed.keyboard import Keystroke
    ks = Keystroke(ucs=u'x', code=1, name=u'the X')
    assert ks._name is u'the X'
    assert ks.name == ks._name
    assert ks._code is 1
    assert ks.code == ks._code
    assert u'xx' == u'x' + ks
    assert ks.is_sequence is True
    assert repr(ks) == "the X"


def test_get_keyboard_codes():
    """Test all values returned by get_keyboard_codes are from curses."""
    from blessed.keyboard import (
        get_keyboard_codes,
        CURSES_KEYCODE_OVERRIDE_MIXIN,
    )
    exemptions = dict(CURSES_KEYCODE_OVERRIDE_MIXIN)
    for value, keycode in get_keyboard_codes().items():
        if keycode in exemptions:
            assert value == exemptions[keycode]
            continue
        assert hasattr(curses, keycode)
        assert getattr(curses, keycode) == value


def test_alternative_left_right():
    """Test alternative_left_right behavior for space/backspace."""
    from blessed.keyboard import _alternative_left_right
    term = mock.Mock()
    term._cuf1 = u''
    term._cub1 = u''
    assert not bool(_alternative_left_right(term))
    term._cuf1 = u' '
    term._cub1 = u'\b'
    assert not bool(_alternative_left_right(term))
    term._cuf1 = u'x'
    term._cub1 = u'y'
    assert (_alternative_left_right(term) == {
        u'x': curses.KEY_RIGHT,
        u'y': curses.KEY_LEFT})


def test_cuf1_and_cub1_as_RIGHT_LEFT(all_terms):
    """Test that cuf1 and cub1 are assigned KEY_RIGHT and KEY_LEFT."""
    from blessed.keyboard import get_keyboard_sequences

    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        keymap = get_keyboard_sequences(term)
        if term._cuf1:
            assert term._cuf1 != u' '
            assert term._cuf1 in keymap
            assert keymap[term._cuf1] == term.KEY_RIGHT
        if term._cub1:
            assert term._cub1 in keymap
            if term._cub1 == '\b':
                assert keymap[term._cub1] == term.KEY_BACKSPACE
            else:
                assert keymap[term._cub1] == term.KEY_LEFT

    child(all_terms)


def test_get_keyboard_sequences_sort_order(xterms):
    @as_subprocess
    def child():
        term = TestTerminal(force_styling=True)
        maxlen = None
        for sequence, code in term._keymap.items():
            if maxlen is not None:
                assert len(sequence) <= maxlen
            assert sequence
            maxlen = len(sequence)
    child()


def test_resolve_sequence():
    """Test resolve_sequence for order-dependent mapping."""
    from blessed.keyboard import resolve_sequence, OrderedDict
    mapper = OrderedDict(((u'SEQ1', 1),
                          (u'SEQ2', 2),
                          # takes precedence over LONGSEQ, first-match
                          (u'KEY_LONGSEQ_longest', 3),
                          (u'LONGSEQ', 4),
                          # wont match, LONGSEQ is first-match in this order
                          (u'LONGSEQ_longer', 5),
                          # falls through for L{anything_else}
                          (u'L', 6)))
    codes = {1: u'KEY_SEQ1',
             2: u'KEY_SEQ2',
             3: u'KEY_LONGSEQ_longest',
             4: u'KEY_LONGSEQ',
             5: u'KEY_LONGSEQ_longer',
             6: u'KEY_L'}
    ks = resolve_sequence(u'', mapper, codes)
    assert ks == u''
    assert ks.name is None
    assert ks.code is None
    assert ks.is_sequence is False
    assert repr(ks) == u"u''"

    ks = resolve_sequence(u'notfound', mapper=mapper, codes=codes)
    assert ks == u'n'
    assert ks.name is None
    assert ks.code is None
    assert ks.is_sequence is False
    assert repr(ks) == u"u'n'"

    ks = resolve_sequence(u'SEQ1', mapper, codes)
    assert ks == u'SEQ1'
    assert ks.name == u'KEY_SEQ1'
    assert ks.code is 1
    assert ks.is_sequence is True
    assert repr(ks) == u"KEY_SEQ1"

    ks = resolve_sequence(u'LONGSEQ_longer', mapper, codes)
    assert ks == u'LONGSEQ'
    assert ks.name == u'KEY_LONGSEQ'
    assert ks.code is 4
    assert ks.is_sequence is True
    assert repr(ks) == u"KEY_LONGSEQ"

    ks = resolve_sequence(u'LONGSEQ', mapper, codes)
    assert ks == u'LONGSEQ'
    assert ks.name == u'KEY_LONGSEQ'
    assert ks.code is 4
    assert ks.is_sequence is True
    assert repr(ks) == u"KEY_LONGSEQ"

    ks = resolve_sequence(u'Lxxxxx', mapper, codes)
    assert ks == u'L'
    assert ks.name == u'KEY_L'
    assert ks.code is 6
    assert ks.is_sequence is True
    assert repr(ks) == u"KEY_L"

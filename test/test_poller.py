# $Header: //prod/main/ap/shrapnel/test/test_poller.py#1 $

"""Unittests for the poller."""

import coro
import coro_process
import coro_unittest
import os
import unittest

class Test(unittest.TestCase):

    def test_wait_for_interrupt_new(self):
        # Test KEVENT_STATUS_NEW
        proc = coro_process.spawn_job_bg('sleep 30')
        def waiter():
            proc.wait()
        waiter_thread = coro.spawn(waiter)
        def killer():
            waiter_thread.shutdown()
        coro.spawn(killer)
        # Waiter should be scheduled to run.
        # It will add kevent to changelist, then yield.
        # Then killer should be scheduled to run next.  It
        # will reschedule waiter with an exception.
        # Waiter should then wake up and hit the
        # KEVENT_STATUS_NEW cleanup code path.
        coro.yield_slice()
        # If we reach here, good.
        # Even better, after the unittest process exits, if there are no
        # core dumps, things are good.

    def test_wait_for_interrupt_submitted(self):
        # Test KEVENT_STATUS_SUBMITTED
        proc = coro_process.spawn_job_bg('sleep 30')
        def waiter():
            proc.wait()
        waiter_thread = coro.spawn(waiter)
        coro.yield_slice()
        # Waiter has submitted its kevent.
        # Interrupt it before it fires.
        waiter_thread.shutdown()
        coro.yield_slice()
        # If we reach here, good.
        # Even better if the process doesn't crash.

    def test_wait_for_interrupted_fired(self):
        # Test KEVENT_STATUS_FIRED
        # This is tricky, need two coroutines to be scheduled at the same time,
        # the first one a normal one and the second one as a result of a kevent
        # firing (in that specific order).
        read_fd1, write_fd1 = os.pipe()
        read_fd2, write_fd2 = os.pipe()
        try:
            read_sock1 = coro.sock(fd=read_fd1)
            read_sock2 = coro.sock(fd=read_fd2)
            # We're going to have two threads.  Since we can't guarantee
            # which one will show up in kqueue first, we'll just have it
            # interrupt the other one, and verify that only one ran.
            sleeper1_thread = None
            sleeper2_thread = None
            sleeper1_data = []
            sleeper2_data = []

            def sleeper1():
                data = read_sock1.read(10)
                sleeper1_data.append(data)
                sleeper2_thread.shutdown()

            def sleeper2():
                data = read_sock2.read(10)
                sleeper2_data.append(data)
                sleeper1_thread.shutdown()

            sleeper1_thread = coro.spawn(sleeper1)
            sleeper2_thread = coro.spawn(sleeper2)

            coro.yield_slice()
            # Both are waiting, wake them both up.
            os.write(write_fd1, 'sleeper1')
            os.write(write_fd2, 'sleeper2')
            coro.yield_slice()
            # Yield again to ensure the shutdown runs.
            coro.yield_slice()

            self.assertTrue(len(sleeper1_data) == 1 or
                            len(sleeper2_data) == 1)
            self.assertTrue(sleeper1_thread.dead)
            self.assertTrue(sleeper2_thread.dead)
        finally:
            os.close(read_fd1)
            os.close(write_fd1)
            os.close(read_fd2)
            os.close(write_fd2)



if __name__ == '__main__':
    coro_unittest.run_tests()

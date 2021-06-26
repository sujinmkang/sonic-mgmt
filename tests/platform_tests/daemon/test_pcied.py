"""
Check daemon status inside PMON container. Each daemon status is checked under the conditions below in this script:
* Daemon Running Status 
* Daemon Stop status
* Daemon Restart status

This script is to cover the test case in the SONiC platform daemon and service test plan:
https://github.com/Azure/sonic-mgmt/blob/master/docs/testplan/PMON-Services-Daemons-test-plan.md
"""
import logging
import re
import time

from datetime import datetime

import pytest

from tests.common.helpers.assertions import pytest_assert
from tests.common.platform.processes_utils import wait_critical_processes, check_critical_processes

expected_running_status = "RUNNING"
expected_stopped_status = "STOPPED"
expected_exited_status = "EXITED"

daemon_name = "pcied"

SIG_STOP_SERVICE = None
SIG_TERM = "-15"
SIG_KILL = "-9"


@pytest.fixture(scope="module", autouse=True)
def teardown_module(duthosts, rand_one_dut_hostname):
    duthost = duthosts[rand_one_dut_hostname]
    yield

    daemon_status, daemon_pid = duthost.get_pmon_daemon_status(daemon_name)
    if daemon_status is not "RUNNING":
        duthost.start_pmon_daemon(daemon_name)
        time.sleep(10)
    logging.info("Tearing down: to make sure all the critical services, interfaces and transceivers are good")
    check_critical_processes(duthost, watch_secs=10)


@pytest.fixture(scope="module", autouse=True)
def disable_and_enable_autorestart(duthosts, rand_one_dut_hostname):
    duthost = duthosts[rand_one_dut_hostname]
    """Changes the autorestart of containers from `enabled` to `disabled` before testing.
       and Rolls them back after testing.
    Args:
        duthost: Hostname of DUT.
    Returns:
        None.
    """
    containers_autorestart_states = duthost.get_container_autorestart_states()
    disabled_autorestart_containers = []

    for container_name, state in containers_autorestart_states.items():
        if state == "enabled":
            logging.info("Disabling the autorestart of container '{}'.".format(container_name))
            command_disable_autorestart = "sudo config feature autorestart {} disabled".format(container_name)
            command_output = duthost.shell(command_disable_autorestart)
            exit_code = command_output["rc"]
            pytest_assert(exit_code == 0, "Failed to disable the autorestart of container '{}'".format(container_name))
            logging.info("The autorestart of container '{}' was disabled.".format(container_name))
            disabled_autorestart_containers.append(container_name)

    yield

    for container_name in disabled_autorestart_containers:
        logging.info("Enabling the autorestart of container '{}'...".format(container_name))
        command_output = duthost.shell("sudo config feature autorestart {} enabled".format(container_name))
        exit_code = command_output["rc"]
        pytest_assert(exit_code == 0, "Failed to enable the autorestart of container '{}'".format(container_name))
        logging.info("The autorestart of container '{}' is enabled.".format(container_name))

@pytest.fixture()
def check_daemon_status(duthosts, rand_one_dut_hostname):
    duthost = duthosts[rand_one_dut_hostname]
    daemon_status, daemon_pid = duthost.get_pmon_daemon_status(daemon_name)
    if daemon_status is not "RUNNING":
        duthost.start_pmon_daemon(daemon_name)
        time.sleep(10)

def test_pmon_pcied_running_status(duthosts, rand_one_dut_hostname):
    """
    @summary: This test case is to check pcied status on dut
    """
    duthost = duthosts[rand_one_dut_hostname]
    daemon_status, daemon_pid = duthost.get_pmon_daemon_status(daemon_name)
    pytest_assert(daemon_status == expected_running_status,
                          "Pcied expected running status is {} but is {}".format(expected_running_status, daemon_status))
    pytest_assert(daemon_pid != -1,
                          "Pcied expected pid is a positive integer but is {}".format(daemon_pid))


def test_pmon_daemon_stop_and_start_status(check_daemon_status, duthosts, rand_one_dut_hostname):
    """
    @summary: This test case is to check the pcied stopped and restarted status 
    """
    duthost = duthosts[rand_one_dut_hostname]
    duthost.stop_pmon_daemon(daemon_name, SIG_STOP_SERVICE)
    time.sleep(2)
    daemon_status, daemon_pid = duthost.get_pmon_daemon_status(daemon_name)
    pytest_assert(daemon_status == expected_stopped_status,
                          "Pcied expected stopped status is {} but is {}".format(expected_stopped_status, daemon_status))
    pytest_assert(daemon_pid == -1,
                          "Pcied expected pid is -1 but is {}".format(daemon_pid))

    duthost.start_pmon_daemon(daemon_name)
    time.sleep(10)
    daemon_status, daemon_pid = duthost.get_pmon_daemon_status(daemon_name)
    pytest_assert(daemon_status == expected_running_status,
                          "Pcied expected restarted status is {} but is {}".format(expected_running_status, daemon_status))
    pytest_assert(daemon_pid == -1,
                          "Pcied expected pid is -1 but is {}".format(daemon_pid))


def test_pmon_daemon_term_and_start_status(check_daemon_status, duthosts, rand_one_dut_hostname):
    """
    @summary: This test case is to check the pcied terminated and restarted status
    """
    duthost = duthosts[rand_one_dut_hostname]
    result = duthost.stop_pmon_daemon(daemon_name, SIG_TERM)
    pytest_assert(result == True, "Stop {} daemon returns {}".format(daemon_name, result))
    daemon_status = duthost.get_pmon_daemon_status(daemon_name)
    pytest_assert(daemon_status == expected_exited_status,
                          "Pcied expected terminated status is {} but is {}".format(expected_exited_status, daemon_status))

    duthost.start_pmon_daemon(daemon_name)
    time.sleep(10)
    daemon_status, daemon_pid = duthost.get_pmon_daemon_status(daemon_name)
    pytest_assert(daemon_status == expected_running_status,
                          "Pcied expected restarted status is {} but is {}".format(expected_running_status, daemon_status))
    pytest_assert(daemon_pid == -1,
                          "Pcied expected pid is -1 but is {}".format(daemon_pid))

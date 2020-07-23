import asyncio
import logging
import os

import hid

from joycontrol import logging_default as log
from joycontrol.report import InputReport, OutputReport, OutputReportID, SubCommand
from joycontrol.utils import AsyncHID

logger = logging.getLogger(__name__)

VENDOR_ID = 1406
PRODUCT_ID_JL = 8198
PRODUCT_ID_JR = 8199
PRODUCT_ID_PC = 8201


"""
Sends some vibration reports to a joycon. Only works with the right joycon atm. 
"""

async def print_outputs(hid_device):
    while True:
        data = await hid_device.read(255)
        # add byte for input report
        data = b'\xa1' + data

        input_report = InputReport(list(data))
        vibrator_input = input_report.data[13]
        # print(hex(vibrator_input))


async def send_vibration_report(hid_device):
    reader = asyncio.ensure_future(print_outputs(hid_device))

    CHANGE_INPUT_REPORT_MODE = [1, 8, 0, 0, 0, 0, 0, 1, 64, 64, 3, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    data = CHANGE_INPUT_REPORT_MODE
    print('writing', data)
    await hid_device.write(bytes(data))
    await asyncio.sleep(0.1)

    report = OutputReport()
    report.set_timer(1)
    report.set_output_report_id(OutputReportID.SUB_COMMAND)
    report.set_sub_command(SubCommand.ENABLE_VIBRATION)
    report.set_sub_command_data([0x01])
    data = bytes(report)[1:]

    print('writing', data)
    await hid_device.write(bytes(data))
    await asyncio.sleep(0.1)

    time = 2
    while True:
        for i in range(10):
            rumble_report = OutputReport()
            report.set_timer(time)
            time += 1
            rumble_report.set_output_report_id(OutputReportID.RUMBLE_ONLY)
            # increase frequency
            rumble_report.set_right_rumble_data(100 + i * 100, 1)
            data = bytes(rumble_report)[1:]
            print('writing', data)
            await hid_device.write(bytes(data))

            await asyncio.sleep(.5)
        break

    try:
        await reader
    except KeyboardInterrupt:
        pass


async def _main(loop):
    logger.info('Waiting for HID devices... Please connect one JoyCon (left OR right), or a Pro Controller over Bluetooth. '
                'Note: The bluez "input" plugin needs to be enabled (default)')

    controller = None
    while controller is None:
        for device in hid.enumerate(0, 0):
            # looking for devices matching Nintendo's vendor id and JoyCon product id
            if device['vendor_id'] == VENDOR_ID and device['product_id'] in (PRODUCT_ID_JL, PRODUCT_ID_JR, PRODUCT_ID_PC):
                controller = device
                break
        else:
            await asyncio.sleep(2)

    logger.info(f'Found controller "{controller}".')

    with AsyncHID(path=controller['path'], loop=loop) as hid_controller:
        await send_vibration_report(hid_controller)


if __name__ == '__main__':
    # check if root
    if not os.geteuid() == 0:
        raise PermissionError('Script must be run as root!')

    # setup logging
    log.configure()

    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(_main(loop))

    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        task.cancel()
        try:
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
    finally:
        loop.stop()
        loop.close()
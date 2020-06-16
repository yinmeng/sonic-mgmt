# How to run test_testbed.py

<code>py.test --inventory ../ansible/msr --host-pattern msr-s6100-dut-1 --module-path ../ansible/library/ --testbed vms16-8 --testbed_file ../ansible/testbed.csv --show-capture=stdout --log-cli-level warning --showlocals -ra --allow_recover --skip_sanity ixia/test_testbed.py</code>

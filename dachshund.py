#!/home/stephan/.virtualenvs/dh/bin/python
import dachshund.__main__

exitcode = dachshund.__main__.run()
print("dachshund exited with return code:", exitcode)

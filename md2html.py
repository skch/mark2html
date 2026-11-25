import sys

from common.rails_context import RailsContext
from domain.config_reader import ConfigReader
from domain.main_service import MainService

VERSION = '1.0.28'

def main():
	print(f'Markdown to HTML. Version {VERSION}')
	context = RailsContext()
	cfg = ConfigReader()
	service = MainService()
	cfg.load_config(context)
	service.execute(context, cfg)
	if context.hasError():
		context.printError()
		sys.exit(1)
	else:
		print('Done')


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
	main()

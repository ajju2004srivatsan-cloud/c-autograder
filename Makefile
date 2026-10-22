.PHONY: test grade grade-all clean

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

grade:
	python3 -m autograder.cli submissions/add.c --rules rules/add_two_integers.json --out-dir reports/

grade-all:
	python3 -c "from autograder.batch import evaluate_directory; evaluate_directory('submissions', 'rules/add_two_integers.json', 'reports')"

clean:
	rm -rf build/ dist/ *.egg-info

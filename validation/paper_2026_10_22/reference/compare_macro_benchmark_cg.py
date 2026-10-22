import os
import sys
import json
import csv

def read_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.loads(f.read())

def measure_precision(actual, expected):
    num_all = 0
    num_caught = 0
    for node in actual:
        num_all += len(actual[node])
        for item in actual[node]:
            if expected.get(node, None) == None:
                continue
            if item in expected[node]:
                num_caught += 1

    if num_all == 0:
        num_all = 1

    return float(num_caught) / float(num_all)

def measure_recall(actual, expected):
    num_all = 0
    num_caught = 0
    for node in expected:
        num_all += len(expected[node])
        for item in expected[node]:
            if actual.get(node, None) == None:
                continue
            if item in actual[node]:
                num_caught += 1

    if num_all == 0:
        num_all = 1
    return float(num_caught) / float(num_all)

def write_results(data, results_path):
    header = ["Project", "Precision", "Recall"]
    prec_sum = 0
    rec_sum = 0
    cnt = 0
    with open(results_path, "w+") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow(header)
        for project, dt in data.items():
            writer.writerow([project, dt["precision"], dt["recall"]])
            try:
                float(dt["precision"])
                float(dt["recall"])
                prec_sum += dt["precision"]
                rec_sum += dt["recall"]
                cnt += 1
            except:
                continue
        writer.writerow(["Average", round(prec_sum/cnt,1),
            round(rec_sum/cnt,1)])

def compare(actual_path, expected_path, results_path):
    projects = ["autojump", "fabric", "asciinema",
            "face_classification", "Sublist3r"]

    prec_sum = 0
    rec_sum = 0
    cnt = 0
    data = {}
    for project in projects:
        actual = read_json(os.path.join(actual_path, project + ".json"))
        expected = read_json(os.path.join(expected_path, project + ".json"))

        if not actual or not expected:
            data[project] = {
                "precision": "-",
                "recall": "-"
            }
            continue

        precision = measure_precision(actual, expected)
        recall = measure_recall(actual, expected)
        data[project] = {
            "precision": round(precision*100,1),
            "recall": round(recall*100,1)
        }

    write_results(data, results_path)


def main():
    if len(sys.argv) < 6:
        print ("Usage compare_macro_benchmark_cg.py pycg_path pyan_path depends_path ground_truth results")
        sys.exit(1)

    pycg_path = sys.argv[1]
    pyan_path = sys.argv[2]
    depends_path = sys.argv[3]
    ground_truth_path = sys.argv[4]
    results_path = sys.argv[5]

    pycg_results = os.path.join(results_path, "pycg_macro_benchmark_eval.csv")
    pyan_results = os.path.join(results_path, "pyan_macro_benchmark_eval.csv")
    depends_results = os.path.join(results_path, "depends_macro_benchmark_eval.csv")

    print ("Generating results for PyCG...")
    print ("-" * 40)
    compare(pycg_path, ground_truth_path, pycg_results)
    print ("\n")

    print ("Generating results for Pyan...")
    print ("-" * 40)
    compare(pyan_path, ground_truth_path, pyan_results)
    print ("\n")

    print ("Generating results for Depends...")
    print ("-" * 40)
    compare(depends_path, ground_truth_path, depends_results)
    print ("\n")

if __name__ == "__main__":
    main()

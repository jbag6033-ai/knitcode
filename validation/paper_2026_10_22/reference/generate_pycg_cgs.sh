#! /bin/bash

if [ -z $1 ]; then
    echo "You have to provide the path to the macro-benchmark directory"
    exit 1
fi

if [ -z $2 ]; then
    echo "You have to provide the path to the results directory"
    exit 1
fi

function start_time()
{
    STARTTIME=$(date +%s%N)
}

function end_time()
{
    ENDTIME=$(date +%s%N)
    ELAPSED=$(echo "scale=2; ($ENDTIME - $STARTTIME) / 10^9" | bc -l)
}

mb_dir=$(realpath $1)
results_file="$(realpath $2)/pycg_macro_benchmark_time.csv"


# create a temporary directory to store the call graphs
mkdir -p ~/tmp
cp -r $mb_dir/projects/{Sublist3r,asciinema,autojump,fabric,face_classification} ~/tmp/

# create directory that will store the PyCG call graphs
pycg_cgs_dir="$mb_dir/pycg-cgs"
mkdir -p $pycg_cgs_dir

echo "Generating call graph for: autojump"
echo "==================================="
py_files=$(find ~/tmp/autojump/bin -type f -name "*.py")
start_time
pycg --package ~/tmp/autojump/bin/ $py_files > $pycg_cgs_dir/autojump.json
end_time
autojump_time=$ELAPSED
echo -e "\n"

echo "Generating call graph for: fabric"
echo "================================="
py_files=$(find ~/tmp/fabric/ -type f -name "*.py" | grep -v tests | grep -v setup.py)
start_time
pycg --package /home/pycg/tmp/fabric/ $py_files > $pycg_cgs_dir/fabric.json
end_time
fabric_time=$ELAPSED
echo -e "\n"

echo "Generating call graph for: asciinema"
echo "===================================="
py_files=$(find ~/tmp/asciinema/asciinema -type f -name "*.py")
start_time
pycg --package ~/tmp/asciinema/ $py_files > $pycg_cgs_dir/asciinema.json
end_time
asciinema_time=$ELAPSED
echo -e "\n"
 
echo "Generating call graph for: face_classification"
echo "=============================================="
py_files=$(find ~/tmp/face_classification/src/ -type f -name "*.py")
start_time
pycg --package ~/tmp/face_classification/src/ $py_files > $pycg_cgs_dir/face_classification.json
end_time
face_classification_time=$ELAPSED
echo -e "\n"

echo "Generating call graph for: Sublist3r"
echo "===================================="
py_files=$(find ~/tmp/Sublist3r -type f -name "*.py")
start_time
pycg --package ~/tmp/Sublist3r/ $py_files > $pycg_cgs_dir/Sublist3r.json
end_time
sublist3r_time=$ELAPSED
echo -e "\n"

rm -r ~/tmp

touch $results_file
echo "Project,Time" > $results_file
echo "autojump,$autojump_time" >> $results_file
echo "fabric,$fabric_time" >> $results_file
echo "asciinema,$asciinema_time" >> $results_file
echo "face_classification,$face_classification_time" >> $results_file
echo "Sublist3r,$sublist3r_time" >> $results_file

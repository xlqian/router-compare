PATH=$WORKSPACE/venv/bin:/usr/local/bin:$PATH

. venv/bin/activate

cd jormungandr_bench

export NAVITIA_API_URL='http://navitia2-ws.ctp.dev.canaltp.fr/v1'
export TOKEN='f4b98e72-9769-400b-b541-05e2e2b30e8c'

export DISTANT_BENCH_OUTPUT='Navitia-Multimodal-Bench-Output'
export LAUNCH_DATETIME=`date "+%Y%m%dT%H%M"`

multimodal='first_section_mode[]=walking&first_section_mode[]=bike&first_section_mode[]=car&last_section_mode[]=walking'

export COVERAGE='fr-auv'
export OUTPUT_DIR=$DISTANT_BENCH_OUTPUT/output/$COVERAGE/$LAUNCH_DATETIME
python bench.py bench --input bench_data/$COVERAGE/benchmark_requests.csv -a $multimodal

export COVERAGE='stif'
export OUTPUT_DIR=$DISTANT_BENCH_OUTPUT/output/$COVERAGE/$LAUNCH_DATETIME
python bench.py bench --input bench_data/$COVERAGE/benchmark_requests.csv -a $multimodal

export COVERAGE='fr-cen'
export OUTPUT_DIR=$DISTANT_BENCH_OUTPUT/output/$COVERAGE/$LAUNCH_DATETIME
python bench.py bench --input bench_data/$COVERAGE/benchmark_requests.csv -a $multimodal


# push bench output to distant repository
cd $DISTANT_BENCH_OUTPUT
git add .
if git commit -m $LAUNCH_DATETIME;
	then git push origin master
fi

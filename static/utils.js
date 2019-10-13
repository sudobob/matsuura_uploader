$(document).ready(() => {

	var idle_counter = 0;
	var idle_secs = 10;

	function show_loader() {
			$('#message_div').html(mesg('fa-cog fa-spin','','warning'));
	}

	function mesg(i,m,c) {
		// primary, secondary, success, danger, warning, info, light, dark
		o  = '';
		o += '<div class="row">';
		o += '<div class="col-md-12">';
		o += '  <div class="alert alert-' + c + '" role="alert">';
		ic = i;
		o += '<i class="fas ' + ic + ' fa-2x">';
		o += '</i>';
		o += '<span style="vertical-align:middle">';
		o += '&nbsp;&nbsp';
		o += m;
		o += '</span>';
		o += '  </div>';
		o += '  </div>';
		o += '</div>';
		return o;
	}

	$(document).on('click','#send_start_btn', () => {
		$.ajax( {
			type: 'PUT',
			url: '/api',
			data: 'cmd=start&file=' + $('#send_start_btn').val(),
			beforeSend: () => { 
				show_loader();

				idle_counter = idle_secs;
			},
			success: (r) => { 
				if (r['error'] == 1) {
					$('#message_div').html(mesg('fa-bomb',r['message'],'danger'));
				} else {
					$('#message_div').html(mesg('fa-rocket',r['message'],'success'));
				}

			}
		});
	});

	$(document).on('click','#send_stop_btn', () => {
		$.ajax( {
			type: 'PUT',
			url: '/api',
			data: 'cmd=stop',
			beforeSend: () => { 
				show_loader();
				idle_counter = idle_secs;
},
			success: (r) => { 
				if (r['error'] == 1) {
					$('#message_div').html(mesg('fa-bomb',r['message'],'danger'));
				} else {
					$('#message_div').html(mesg('fa-rocket',r['message'],'success'));
				}

			}
		});
	});


	$(document).on('click','#send_status_btn', () => {
			//$('#message_div').html(mesg('binoculars','status','warning'));
			$('#message_div').html(mesg('fa-binoculars ','','warning'));
	});

	function get_status() {

	}

	function periodic_chores() {
		// tend to periodic housekeeping chores
		if (idle_counter) 
			idle_counter--;
		if (idle_counter == 0) {
			idle_counter = idle_secs; 
		}
		console.log('periodic_chores() idle_counter:' + idle_counter);
	}

	setInterval(periodic_chores,  1000);

});

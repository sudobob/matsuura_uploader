$(document).ready(() => {

  var idle_counter = 0;
  var last_status_message = ''
  var idle_intrvl_sending_secs = 2;
  var idle_intrvl_idle_secs = 5;
  var idle_intrvl_secs = idle_intrvl_idle_secs;

  function show_loader() {
    $('#message_div').html(mesg('fa-cog fa-spin','','warning'));
  }

  function mesg(i,m,c) {
    // primary, secondary, success, danger, warning, info, light, dark
    let o = '';
    o += '<div class="row">';
    o += '<div class="col-md-12">';
    o += '  <div class="alert alert-' + c + '" role="alert">';
    ic = i;
    o += '<span style="vertical-align:top;font-size:1.5em">';
    o += '<i class="fas ' + ic + ' fa-2x">';
    o += '</i>';
    o += '<span style="vertical-align:top">';
    o += '&nbsp;&nbsp';
    o += m;
    o += '</span>';
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
        idle_counter = 0;
      },
      success: (r) => { 
        if (r['error'] == 1) {
          $('#message_div').html(mesg('fa-bomb',r['message'],'danger'));
        } else {
          $('#message_div').html(mesg('fa-rocket',r['message'],'success'));
          idle_intrvl_secs = idle_intrvl_sending_secs;
        }
        last_status_message = r['message']
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
        idle_counter = 0;
      },
      success: (r) => { 
        if (r['error'] == 1) {
          $('#message_div').html(mesg('fa-bomb',r['message'],'danger'));
        } else {
          $('#message_div').html(mesg('fa-rocket',r['message'],'success'));
        }
        last_status_message = r['message']
      }
    });
  });

  $(document).on('click','#send_status_btn', () => {
    get_status();
  });

  function get_status() {
    //$('#message_div').html(mesg('fa-binoculars ','under construction','warning'));
    $.ajax( {
      type: 'PUT',
      url: '/api',
      data: 'cmd=status',
      beforeSend: () => { 
        show_loader();
        idle_counter = 0;
      },
      success: (r) => { 
        if (r['error'] == 1) {
          $('#message_div').html(mesg('fa-bomb',r['message'],'danger'));
        } else {
          $('#message_div').html(mesg('fa-binoculars',r['message'],'success'));
        }
        last_status_message = r['message']
      }
    });
  }

  function periodic_chores() {
    // tend to periodic housekeeping chores
    idle_counter++;
    if (idle_counter >= idle_intrvl_secs) {
      idle_counter = 0;
      get_status();
    }
    console.log('periodic_chores() idle_counter:' + idle_counter + ' last_status_message:' + last_status_message);

    if (last_status_message.match(/Sending/i))
      idle_intrvl_secs = idle_intrvl_sending_secs;
    else
      idle_intrvl_secs = idle_intrvl_idle_secs;
  }

  setInterval(periodic_chores,  1000);

  get_status();

});

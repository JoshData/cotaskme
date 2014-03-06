function show_modal_error(title, message) {
	$('#error_modal h4').text(title);
	$('#error_modal p').text(message);
	$('#error_modal').modal({});
}

var nav_post_err_title = "Post It";

function post_state(state) {
	var elems = $('#nav_post_form input, #nav_post_form select, #nav_post_form textarea, #nav_post_form button');
	elems.prop("disabled", !state);
}

function do_post() {
	if ($('#navPostTitle').val() == "") {
  		show_modal_error(nav_post_err_title, "Type in a title for the task.");
  		return false;
	}

  	$.ajax(
  		"/_post",
  		{
  			data: {
  				title: $('#navPostTitle').val(),
  				notes: "",
  				outgoing: "_default",
  				incoming: "_not_impl"
  			},
  			method: "POST",
  			success: function(res) {
			  	post_state(true);
  				if (res.status != "ok") {
  					show_modal_error(nav_post_err_title, res.msg);
  					return;
  				}

				show_modal_error(nav_post_err_title, "Refresh the page please! :) Task has been posted.");

				// reset fields to prevent double-submit
				$('#navPostTitle').val('');
  			},
  			error: function() {
			  	show_modal_error(nav_post_err_title, "There was an error, sorry.");
			  	post_state(true);
  			}
  		});
	return false;
}
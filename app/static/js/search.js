$(document).ready(function () {
	// Page setup
	var attributeChart = $(".details-attribute-chart");
	var currentGameTagsKeys = [];
	var currentGameTagsValues = [];
	var detailsExpanded = false;
	var detailsRadarChart;
	var selectedAppID;

	if(currentGameTitle !== undefined) {
		$('html, body').animate({scrollTop : $(".results").position().top - 15 }, 400);

		for (var key in currentGameTags) {
			if (!currentGameTags.hasOwnProperty(key)) continue;
			currentGameTagsKeys.push(key);
			currentGameTagsValues.push(currentGameTags[key]);
		}

		var tags_div = $(".tags");
		var search_tags = tags_div.data("tags");
		for (var key in search_tags) {
			if (!search_tags.hasOwnProperty(key)) continue;
			tags_div.append("<p class='tag selected'>" + key + "</p>")
		}
	}

	// Handle event listeners

	// Thanks to: http://stackoverflow.com/questions/28631219/how-can-i-unfocus-the-modal-trigger-button-after-closing-the-modal-in-bootstrap
	$("#login-modal").on("shown.bs.modal", function(e){
    	$('.steam-login').one('focus', function(e){$(this).blur();});
	});

	$(".details-close").click(function() {
		$(".details-content-wrapper").fadeOut(150, function() {
			$(".details-overlay").animate({width:'0px'}, 300);
			detailsExpanded = false;
		});
	});

	$(".details-query").click(function() {
		window.location.replace("/?app_id=" + selectedAppID);
	});

	$(".result-box").click(function() {
		var resultBox = $(this);
		var updateDetails = function() {
			var gameTitle = resultBox.data("title");
			$(".details-title").text(gameTitle);
			$(".details-img").attr("src", resultBox.children(".result-img").attr("src"));
			$(".details-link").attr("href", resultBox.data("steam-url"));

			selectedAppID = resultBox.data("app-id");

			var tags = resultBox.data("tags");
			var tagsKeys = [];
			var tagsValues = [];
			for (var key in tags) {
				if (!tags.hasOwnProperty(key)) continue;
				tagsKeys.push(key);
				tagsValues.push(tags[key]);
			}
			var data = {
			    labels: tagsKeys,
			    datasets: [
			        {
			            label: gameTitle,
			            backgroundColor: "rgba(255,99,132,0.2)",
			            borderColor: "rgba(255,99,132,1)",
			            pointBackgroundColor: "rgba(255,99,132,1)",
			            pointBorderColor: "#fff",
			            pointHoverBackgroundColor: "#fff",
			            pointHoverBorderColor: "rgba(255,99,132,1)",
			            data: tagsValues
			        },
			        {
			            label: currentGameTitle,
			            backgroundColor: "rgba(90, 179, 206, 0.2)",
			            borderColor: "rgba(90, 179, 206, 1)",
			            pointBackgroundColor: "rgba(90, 179, 206, 1)",
			            pointBorderColor: "#fff",
			            pointHoverBackgroundColor: "#fff",
			            pointHoverBorderColor: "rgba(90, 179, 206, 1)",
			            data: currentGameTagsValues
			        }
			    ]
			};

			if(detailsRadarChart !== undefined)
				detailsRadarChart.destroy();

			detailsRadarChart = new Chart(attributeChart, {
				type: 'radar',
			    data: data,
			    options: {
			    	legend: {
			    		position: 'bottom'
			    	},
			    	scale: {
				        ticks: {
				            display: false
				        }
				    },
				    tooltips: {
				    	// enabled: false
				    }
			    }
			});

			$(".details-overlay").animate({width:'400px'}, 300, function() {
				$(".details-content-wrapper").fadeIn(150);
				detailsExpanded = true;
			});
		};

		if(detailsExpanded) {
			var detailsBody = $(".details-body");
			detailsBody.fadeOut(200, function() {
				updateDetails();
				detailsBody.fadeIn(200);
			});
		}
		else
			updateDetails();
	});

	$(".tag").click(function() {
		var tag = $(this);
		if(tag.hasClass("selected"))
			$(this).removeClass("selected");
		else
			$(this).addClass("selected");
	})
});